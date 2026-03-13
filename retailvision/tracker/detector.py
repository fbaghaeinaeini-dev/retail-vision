"""RetailTracker: YOLOv11 + BoTSORT detector-tracker for CCTV.

Processes video into structured tracking data stored in SQLite.
Runs entirely locally with zero network calls.

Key design choices:
- yolo11m.pt: medium model, good balance for 1080p CCTV
- imgsz=1280: higher res catches distant/small people
- conf=0.25: lower threshold for CCTV (people often small/distant)
- BoTSORT with ReID: handles occlusion in crowded retail
- track_buffer=90: 3s persistence for brief disappearances
- Batch DB inserts every 2000 detections for performance
- Keyframe extraction every N frames for downstream VLM analysis
"""

import cv2
import numpy as np
from loguru import logger
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from ultralytics import YOLO

from tracker.config import TrackerConfig
from tracker.database import TrackDatabase


class RetailTracker:
    """Offline person detector-tracker for CCTV footage."""

    BATCH_SIZE = 2000

    def __init__(self, config: TrackerConfig | None = None):
        self.config = config or TrackerConfig()
        self.model = YOLO(self.config.yolo_model)
        self.db = TrackDatabase(self.config.db_path)

    def process_video(self, video_path: str, video_id: str, max_frames: int = 0) -> dict:
        """Process a video file, storing detections and keyframes in SQLite.

        Args:
            video_path: Path to input video file.
            video_id: Unique identifier for this video.
            max_frames: Stop after this many frames (0 = process all).

        Returns:
            Summary dict with frames_processed, detection_count, track_count.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        effective_frames = min(total_frames, max_frames) if max_frames > 0 else total_frames
        self.db.insert_video(video_id, video_path, fps, effective_frames, W, H)
        logger.info(f"Processing {video_path}: {effective_frames}/{total_frames} frames @ {fps:.1f}fps, {W}x{H}")

        frame_idx = 0
        batch: list[dict] = []
        total_detections = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Tracking", total=effective_frames)

            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                # Run detector-tracker
                results = self.model.track(
                    frame,
                    persist=True,
                    tracker=self.config.tracker_yaml,
                    classes=self.config.detect_classes,
                    conf=self.config.detection_conf,
                    iou=self.config.detection_iou,
                    imgsz=self.config.imgsz,
                    verbose=False,
                )

                # Extract detections
                if results[0].boxes.id is not None:
                    boxes = results[0].boxes
                    ids = boxes.id.int().cpu().numpy()
                    xyxy = boxes.xyxy.cpu().numpy()
                    confs = boxes.conf.cpu().numpy()

                    for i, tid in enumerate(ids):
                        x1, y1, x2, y2 = xyxy[i]
                        batch.append(
                            {
                                "video_id": video_id,
                                "frame_idx": frame_idx,
                                "timestamp": frame_idx / fps,
                                "track_id": int(tid),
                                "x_center": float((x1 + x2) / 2),
                                "y_center": float((y1 + y2) / 2),
                                "bbox_x1": float(x1),
                                "bbox_y1": float(y1),
                                "bbox_x2": float(x2),
                                "bbox_y2": float(y2),
                                "bbox_w": float(x2 - x1),
                                "bbox_h": float(y2 - y1),
                                "confidence": float(confs[i]),
                                "object_class": "person",
                            }
                        )

                # Extract keyframe for VLM/depth analysis downstream
                if frame_idx % self.config.keyframe_interval == 0:
                    self.db.insert_keyframe(video_id, frame_idx, frame)

                # Batch insert for performance
                if len(batch) >= self.BATCH_SIZE:
                    self.db.insert_detections_batch(batch)
                    total_detections += len(batch)
                    batch = []

                frame_idx += 1
                progress.update(task, advance=1)

                if max_frames > 0 and frame_idx >= max_frames:
                    break

        # Flush remaining batch
        if batch:
            self.db.insert_detections_batch(batch)
            total_detections += len(batch)

        cap.release()

        # Post-processing
        self.db.compute_track_summaries(video_id)
        self._score_track_quality(video_id)

        track_count = len(self.db.get_track_summaries(video_id))
        logger.success(
            f"Done: {frame_idx} frames, {total_detections} detections, {track_count} tracks"
        )

        return {
            "video_id": video_id,
            "frames_processed": frame_idx,
            "detection_count": total_detections,
            "track_count": track_count,
        }

    def _score_track_quality(self, video_id: str):
        """Score track quality [0, 1] based on duration, count, confidence, completeness, smoothness.

        Tracks with quality < 0.3 are filtered out by the agent pipeline.
        """
        tracks = self.db.get_track_summaries(video_id)
        for t in tracks:
            dur = min(t["duration_seconds"] / 30.0, 1.0)
            cnt = min(t["num_detections"] / 50.0, 1.0)
            conf = t["avg_confidence"]
            comp = t["num_detections"] / max(t["duration_frames"], 1)

            disps = self.db.get_track_displacements(video_id, t["track_id"])
            if len(disps) > 2:
                mean_d = np.mean(disps)
                smooth = max(0.0, 1.0 - np.std(disps) / (mean_d + 1e-6))
            else:
                smooth = 0.5

            quality = 0.25 * dur + 0.20 * cnt + 0.20 * conf + 0.15 * comp + 0.20 * smooth
            self.db.update_track_quality(video_id, t["track_id"], float(quality))

        logger.info(f"Scored quality for {len(tracks)} tracks")
