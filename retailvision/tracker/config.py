"""Tracker configuration with sensible CCTV defaults."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class TrackerConfig(BaseSettings):
    """Configuration for Module A (Offline Tracker)."""

    # Model
    yolo_model: str = "yolo11m.pt"
    tracker_yaml: str = str(Path(__file__).parent / "botsort_retail.yaml")
    detect_classes: list[int] = Field(default=[0])  # 0 = person
    detection_conf: float = 0.25
    detection_iou: float = 0.5
    imgsz: int = 1280

    # Database
    db_path: Path = Path("data/retailvision.db")

    # Keyframes
    keyframe_interval: int = 150  # Extract keyframe every N frames

    # Quality
    track_quality_threshold: float = 0.3

    model_config = {"env_file": ".env", "env_prefix": "", "extra": "ignore"}
