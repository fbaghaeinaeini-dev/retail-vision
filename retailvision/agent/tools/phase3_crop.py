"""Phase 3 Tool t13: Crop zone images for VLM analysis."""

import base64

import cv2
import numpy as np
from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("crop_zone_images")
def crop_zone_images(state, config) -> ToolResult:
    """t13: Extract standard and wide-margin crops for each zone.

    Standard crop: +20% margin around zone bbox
    Wide crop: +40% margin (captures overhead signage)
    Both encoded as base64 JPEG for VLM consumption.
    """
    if state.reference_frame is None:
        return ToolResult(success=False, message="No reference frame")

    frame = state.reference_frame
    H, W = frame.shape[:2]
    standard_margin = config.vlm_crop_margin_pct
    wide_margin = config.vlm_wide_margin_pct

    zone_crops = {}

    zones = state.fused_zones_dict or state.zone_registry_draft
    for zone_id, zone in zones.items():
        bbox = zone.get("bbox_pixel", [0, 0, W, H])
        x1, y1, x2, y2 = bbox

        # Standard crop with margin
        std_crop = _crop_with_margin(frame, x1, y1, x2, y2, standard_margin, W, H)
        std_b64 = _encode_crop(std_crop)

        # Wide crop for signage above
        wide_crop = _crop_with_margin(frame, x1, y1, x2, y2, wide_margin, W, H)
        wide_b64 = _encode_crop(wide_crop)

        zone_crops[zone_id] = {
            "standard": std_b64,
            "wide": wide_b64,
            "standard_shape": std_crop.shape,
            "wide_shape": wide_crop.shape,
        }

    state.zone_crops = zone_crops

    return ToolResult(
        success=True,
        data={"n_crops": len(zone_crops)},
        message=f"Cropped {len(zone_crops)} zones (standard +{standard_margin:.0%}, wide +{wide_margin:.0%})",
    )


def _crop_with_margin(
    frame: np.ndarray,
    x1: float, y1: float, x2: float, y2: float,
    margin_pct: float,
    W: int, H: int,
) -> np.ndarray:
    """Extract a crop with percentage margin around a bbox."""
    w = x2 - x1
    h = y2 - y1
    mx = w * margin_pct
    my = h * margin_pct

    cx1 = max(0, int(x1 - mx))
    cy1 = max(0, int(y1 - my))
    cx2 = min(W, int(x2 + mx))
    cy2 = min(H, int(y2 + my))

    crop = frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return frame  # Fallback to full frame

    return crop


def _encode_crop(crop: np.ndarray) -> str:
    """Encode crop to base64 JPEG."""
    _, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")
