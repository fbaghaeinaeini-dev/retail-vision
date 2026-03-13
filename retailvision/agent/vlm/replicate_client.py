"""Replicate clients for Depth estimation and Language-Segment-Anything.

Handles image encoding, API calls, and output parsing.
Gracefully degrades when API is not available.
"""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
from loguru import logger
from PIL import Image


def _read_replicate_output(output, prefer_key: str | None = None) -> bytes | None:
    """Read raw bytes from a Replicate model output.

    Handles all output formats from Replicate SDK v1.x:
    - FileOutput objects (have .read() and .url)
    - Dict of FileOutput/URL values (e.g. depth model returns {"grey_depth": ..., "color_depth": ...})
    - Plain URL strings
    - data: URIs
    - Iterators of FileOutput objects
    """
    import httpx

    def _read_item(item) -> bytes | None:
        # FileOutput: try .url first (more reliable with custom timeout)
        if hasattr(item, "url") and isinstance(item.url, str):
            url = item.url
            if url.startswith("data:"):
                _, encoded = url.split(",", 1)
                return base64.b64decode(encoded)
            if url.startswith(("http://", "https://")):
                resp = httpx.get(url, timeout=180)
                resp.raise_for_status()
                return resp.content
        # Fallback: use .read() for non-URL FileOutput
        if hasattr(item, "read") and callable(item.read):
            try:
                return item.read()
            except Exception as e:
                logger.warning(f"FileOutput.read() failed: {e}")
                return None
        # URL string
        s = str(item)
        if s.startswith("data:"):
            _, encoded = s.split(",", 1)
            return base64.b64decode(encoded)
        if s.startswith(("http://", "https://")):
            resp = httpx.get(s, timeout=120)
            resp.raise_for_status()
            return resp.content
        # Try .url attribute (FileOutput-like)
        if hasattr(item, "url"):
            return _read_item(item.url)
        logger.warning(f"Cannot read Replicate output item: {type(item)} = {s[:100]}")
        return None

    # Dict output (e.g. depth model)
    if isinstance(output, dict):
        target = None
        if prefer_key and prefer_key in output:
            target = output[prefer_key]
        else:
            # Take first non-None value
            for v in output.values():
                if v is not None:
                    target = v
                    break
        if target is not None:
            return _read_item(target)

    # Direct string or FileOutput
    if isinstance(output, str) or hasattr(output, "read"):
        return _read_item(output)

    # Iterator (e.g. list of FileOutput)
    if hasattr(output, "__iter__"):
        for item in output:
            result = _read_item(item)
            if result is not None:
                return result

    return None


class ReplicateDepth:
    """Client for running depth estimation via Replicate API."""

    MODEL_ID = "chenxwh/depth-anything-v2:b239ea33cff32bb7abb5db39ffe9a09c14cbc2894331d1ef66fe096eed88ebd4"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self._available = bool(api_token)

    @property
    def available(self) -> bool:
        return self._available

    def estimate_depth(self, frame: np.ndarray) -> tuple[np.ndarray, float | None]:
        """Run Depth Anything V2 on a frame.

        Args:
            frame: BGR numpy array.

        Returns:
            (depth_map, focal_length) — depth_map is float32 HxW in meters.
            focal_length may be None if not returned by model.
        """
        if not self._available:
            raise RuntimeError("Replicate API not configured")

        import replicate
        import os
        os.environ["REPLICATE_API_TOKEN"] = self.api_token

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=90)
        buf.seek(0)

        logger.info("Running Depth Anything V2 via Replicate...")
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                buf.seek(0)
                output = replicate.run(
                    self.MODEL_ID,
                    input={"image": buf, "model_size": "Large"},
                )
                depth_map = self._parse_output(output, frame.shape[:2])
                return depth_map, None

            except Exception as e:
                err_str = str(e)
                if "429" in err_str and attempt < max_retries - 1:
                    wait = 15 * (attempt + 1)
                    logger.warning(f"Replicate error ({err_str[:60]}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"Replicate depth estimation failed: {e}")
                raise

    def _parse_output(self, output, target_shape: tuple[int, int]) -> np.ndarray:
        """Parse depth output from Replicate into a numpy array.

        Depth Anything V2 returns {"color_depth": url, "grey_depth": url}.
        We use grey_depth for numerical accuracy.
        """
        raw_bytes = _read_replicate_output(output, prefer_key="grey_depth")
        if raw_bytes is None:
            raise ValueError(f"Unexpected Replicate output type: {type(output)}")

        img = Image.open(io.BytesIO(raw_bytes))
        depth = np.array(img, dtype=np.float32)

        # Handle multi-channel depth (take first channel or grayscale)
        if depth.ndim == 3:
            depth = depth[:, :, 0]

        # Depth Anything V2 outputs relative depth (0-255 range)
        # Normalize to approximate metric depth using scene scale
        if depth.max() > 1.0:
            # Relative depth: normalize to 0-1, then scale
            depth = depth / depth.max()
            # Approximate metric: assume max scene depth ~15m for indoor
            depth = depth * 15.0

        if depth.shape[:2] != target_shape:
            depth = cv2.resize(depth, (target_shape[1], target_shape[0]))

        return depth

    def _extract_focal_length(self, output) -> float | None:
        if isinstance(output, dict) and "focal_length" in output:
            return float(output["focal_length"])
        return None


class ReplicateSegmentation:
    """Client for Semantic-Segment-Anything via Replicate API.

    Runs full-scene semantic segmentation in a single call.
    Returns labeled segments with class names, bounding boxes, and masks.
    Results are cached so the model only runs once per frame.
    """

    MODEL_ID = "cjwbw/semantic-segment-anything:b2691db53f2d96add0051a4a98e7a3861bd21bf5972031119d344d956d2f8256"

    # SSA labels to ignore (background/noise, not useful as zone context)
    _IGNORE_LABELS = {"background", "blurry photo", "blurry image", "blurry photograph",
                       "close", "base", "front", "that", "arafed image", "arafed sign"}

    def __init__(self, api_token: str):
        self.api_token = api_token
        self._available = bool(api_token)
        self._cached_segments: list[dict] | None = None
        self._cached_image: np.ndarray | None = None

    @property
    def available(self) -> bool:
        return self._available

    def segment_scene(self, frame: np.ndarray) -> list[dict]:
        """Run full semantic segmentation on a frame (cached).

        Returns list of segment dicts with keys:
        - class_name: semantic label (e.g. "table", "chair", "floor")
        - bbox: [x1, y1, x2, y2] in pixel coords
        - area: approximate area in pixels
        - zone_type: mapped zone type from LABEL_TO_ZONE_TYPE
        """
        if self._cached_segments is not None and self._cached_image is not None:
            if self._cached_image.shape == frame.shape:
                return self._cached_segments

        if not self._available:
            raise RuntimeError("Replicate API not configured")

        import replicate
        import os
        import time
        os.environ["REPLICATE_API_TOKEN"] = self.api_token

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=90)
        buf.seek(0)

        logger.info("Running Semantic-Segment-Anything via Replicate...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                buf.seek(0)
                # Use predictions API for longer timeout control
                import httpx
                client = replicate.Client(api_token=self.api_token)
                model = client.models.get(self.MODEL_ID.split(":")[0])
                version = model.versions.get(self.MODEL_ID.split(":")[1])

                prediction = client.predictions.create(
                    version=version,
                    input={"image": buf, "output_json": True},
                )
                # Wait for prediction with polling
                prediction.wait()

                if prediction.status == "failed":
                    raise RuntimeError(f"SSA prediction failed: {prediction.error}")

                output = prediction.output
                if output is None:
                    raise RuntimeError("SSA returned no output")

                # output is a dict like {"img_out": url, "json_out": url}
                # Download json_out directly with our own httpx client
                json_url = None
                if isinstance(output, dict) and "json_out" in output:
                    json_url = str(output["json_out"])
                elif isinstance(output, dict):
                    # Try any key
                    for v in output.values():
                        json_url = str(v)
                        break

                if json_url and json_url.startswith(("http://", "https://")):
                    logger.info(f"Downloading SSA JSON from: {json_url[:80]}...")
                    resp = httpx.get(json_url, timeout=180)
                    resp.raise_for_status()
                    raw_bytes = resp.content
                else:
                    # Fall back to _read_replicate_output
                    raw_bytes = _read_replicate_output(output, prefer_key="json_out")

                if raw_bytes is None:
                    raise RuntimeError(f"Cannot read SSA output: {type(output)}")

                import json as json_mod
                raw_data = json_mod.loads(raw_bytes)
                segments = self._parse_segments(raw_data)
                self._cached_segments = segments
                self._cached_image = frame
                logger.info(f"SSA found {len(segments)} segments with "
                            f"{len(set(s['class_name'] for s in segments))} unique classes")
                return segments

            except Exception as e:
                err_str = str(e)
                if "429" in err_str and attempt < max_retries - 1:
                    wait = 12 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue
                logger.warning(f"Semantic segmentation failed: {e}")
                return []

        return []

    def segment(self, frame: np.ndarray, text_prompt: str) -> np.ndarray | None:
        """Backward-compatible: get mask for segments matching a text query.

        Runs full segmentation, then filters segments whose class_name
        contains any word from the text_prompt.
        """
        segments = self.segment_scene(frame)
        if not segments:
            return None

        keywords = [w.lower().strip() for w in text_prompt.replace(",", " ").split()]
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        for seg in segments:
            name = seg["class_name"].lower()
            if any(kw in name for kw in keywords):
                bbox = seg["bbox"]
                x1, y1 = max(0, int(bbox[0])), max(0, int(bbox[1]))
                x2, y2 = min(w, int(bbox[2])), min(h, int(bbox[3]))
                mask[y1:y2, x1:x2] = 255

        if mask.max() == 0:
            return None
        return mask

    def segment_multiple(self, frame: np.ndarray, prompts: list[str]) -> dict[str, np.ndarray]:
        """Run segmentation for multiple prompts (single API call).

        Returns dict mapping prompt -> binary mask.
        """
        # Single API call, then filter by each prompt
        self.segment_scene(frame)
        results = {}
        for prompt in prompts:
            mask = self.segment(frame, prompt)
            if mask is not None:
                results[prompt] = mask
        return results

    def get_semantic_labels_for_region(self, frame: np.ndarray, bbox: list) -> list[str]:
        """Return list of SSA semantic labels overlapping with a region.

        Returns raw class names (e.g. ["table", "chair", "floor"]) for the
        VLM classifier to reason about in context. No zone type mapping.
        """
        segments = self.segment_scene(frame)
        if not segments:
            return []

        from shapely.geometry import box as shapely_box
        region_box = shapely_box(bbox[0], bbox[1], bbox[2], bbox[3])
        if region_box.area < 1:
            return []

        labels = set()
        for seg in segments:
            seg_box = shapely_box(*seg["bbox"])
            if not region_box.intersects(seg_box):
                continue
            overlap = region_box.intersection(seg_box).area
            # Only include if significant overlap (>10% of segment)
            if overlap > seg_box.area * 0.1:
                name = seg["class_name"]
                if name not in self._IGNORE_LABELS:
                    labels.add(name)

        return sorted(labels)

    def _parse_segments(self, raw_data) -> list[dict]:
        """Parse SSA JSON data into segment list.

        Args:
            raw_data: Parsed JSON — list of annotations from SSA.
        """
        # SSA JSON format: list of annotations
        segments = []
        annotations = raw_data if isinstance(raw_data, list) else raw_data.get("annotations", [])

        for ann in annotations:
            class_name = ann.get("class_name", ann.get("label", "unknown"))
            # Strip articles ("a restaurant" → "restaurant")
            class_name_clean = class_name.lower().strip()
            for article in ("a ", "an ", "the "):
                if class_name_clean.startswith(article):
                    class_name_clean = class_name_clean[len(article):]

            # SSA bbox format: [x, y, width, height] — convert to [x1, y1, x2, y2]
            raw_bbox = ann.get("bbox", [0, 0, 0, 0])
            if len(raw_bbox) == 4:
                bbox = [raw_bbox[0], raw_bbox[1],
                        raw_bbox[0] + raw_bbox[2], raw_bbox[1] + raw_bbox[3]]
            else:
                bbox = raw_bbox

            area = ann.get("area", 0)
            class_proposals = ann.get("class_proposals", [])

            segments.append({
                "class_name": class_name_clean,
                "class_name_raw": class_name,
                "bbox": bbox,
                "area": area,
                "class_proposals": class_proposals,
            })

        return segments


def colorize_depth_map(depth: np.ndarray) -> np.ndarray:
    """Convert depth map to a colorized BGR image for visualization."""
    valid = depth[depth > 0.1]
    if len(valid) == 0:
        return np.zeros((*depth.shape, 3), dtype=np.uint8)

    vmin, vmax = np.percentile(valid, [2, 98])
    normalized = np.clip((depth - vmin) / (vmax - vmin + 1e-6), 0, 1)
    colored = cv2.applyColorMap((normalized * 255).astype(np.uint8), cv2.COLORMAP_MAGMA)
    colored[depth < 0.1] = 0

    return colored
