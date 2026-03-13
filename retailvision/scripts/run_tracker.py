"""CLI for Module A: Run the offline tracker on a video file.

Usage:
    python -m scripts.run_tracker --video data/footage.mp4 --db data/retailvision.db
"""

import hashlib
from pathlib import Path

import click
from loguru import logger

from tracker.config import TrackerConfig
from tracker.detector import RetailTracker


@click.command()
@click.option("--video", required=True, type=click.Path(exists=True), help="Input video file")
@click.option("--db", default="data/retailvision.db", help="SQLite database path")
@click.option("--model", default="yolo11m.pt", help="YOLO model file")
@click.option("--video-id", default=None, help="Custom video ID (default: hash of filename)")
@click.option("--keyframe-interval", default=150, type=int, help="Keyframe extraction interval")
@click.option("--conf", default=0.25, type=float, help="Detection confidence threshold")
@click.option("--imgsz", default=1280, type=int, help="Input image size")
def main(video, db, model, video_id, keyframe_interval, conf, imgsz):
    """Process a CCTV video through YOLOv11 + BoTSORT tracker."""
    config = TrackerConfig(
        db_path=Path(db),
        yolo_model=model,
        keyframe_interval=keyframe_interval,
        detection_conf=conf,
        imgsz=imgsz,
    )

    if video_id is None:
        # Generate stable ID from filename
        video_id = hashlib.md5(Path(video).name.encode()).hexdigest()[:12]

    logger.info(f"Starting tracker: video={video}, video_id={video_id}")
    tracker = RetailTracker(config)
    result = tracker.process_video(str(video), video_id)

    logger.success(f"Tracker complete: {result}")


if __name__ == "__main__":
    main()
