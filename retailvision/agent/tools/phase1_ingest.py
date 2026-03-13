"""Phase 1 Tools: t01 (ingest_from_db) and t02 (extract_reference_frame).

Load tracking data from SQLite into the agent state.
"""

import struct

import numpy as np
import pandas as pd
from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from tracker.database import TrackDatabase


def _fix_bytes_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any bytes columns (numpy float32 stored as BLOB in SQLite) to float."""
    for col in df.columns:
        if df[col].dtype == object and len(df) > 0:
            sample = df[col].iloc[0]
            if isinstance(sample, bytes) and len(sample) == 4:
                df[col] = df[col].apply(lambda b: struct.unpack('f', b)[0] if isinstance(b, bytes) else b)
                df[col] = df[col].astype(np.float64)
    return df


@ToolRegistry.register("ingest_from_db")
def ingest_from_db(state, config) -> ToolResult:
    """t01: Load tracking data from SQLite database into agent state.

    Reads all detections for the configured video_id, filters by
    track quality, and loads into a pandas DataFrame for downstream tools.
    """
    db = TrackDatabase(config.db_path)
    video = db.get_video(config.video_id)
    if video is None:
        return ToolResult(
            success=False,
            message=f"Video '{config.video_id}' not found in database",
        )

    # Load all detections
    detections = db.get_detections(config.video_id)
    if not detections:
        return ToolResult(success=False, message="No detections found")

    df = pd.DataFrame(detections)

    # Fix bytes columns from numpy float32 stored as BLOB in SQLite
    df = _fix_bytes_columns(df)

    # Load track summaries for quality filtering
    track_summaries = db.get_track_summaries(config.video_id)
    quality_map = {t["track_id"]: t["quality_score"] for t in track_summaries}

    # Filter low-quality tracks
    df["quality"] = df["track_id"].map(quality_map).fillna(0)
    n_before = df["track_id"].nunique()
    df = df[df["quality"] >= config.track_quality_threshold].copy()
    n_after = df["track_id"].nunique()

    # Compute time deltas per track
    df = df.sort_values(["track_id", "frame_idx"]).reset_index(drop=True)
    df["dt"] = df.groupby("track_id")["timestamp"].diff().fillna(0)

    state.raw_tracks = df
    state.video_id = config.video_id
    state.video_duration_seconds = video["duration_seconds"]
    state.frame_shape = (video["height"], video["width"], 3)

    db.close()

    return ToolResult(
        success=True,
        data={
            "total_detections": len(df),
            "tracks_before_filter": n_before,
            "tracks_after_filter": n_after,
            "video_duration_s": video["duration_seconds"],
        },
        message=f"Loaded {len(df)} detections, {n_after}/{n_before} tracks "
                f"(quality >= {config.track_quality_threshold})",
    )


@ToolRegistry.register("extract_reference_frame")
def extract_reference_frame(state, config) -> ToolResult:
    """t02: Extract a reference frame from the middle of the video.

    This frame is used for VLM analysis, depth estimation, and
    zone overlay visualizations.
    """
    db = TrackDatabase(config.db_path)
    result = db.get_reference_frame(config.video_id)
    db.close()

    if result is None:
        return ToolResult(success=False, message="No keyframes found in database")

    frame_idx, frame = result
    state.reference_frame = frame
    state.reference_frame_idx = frame_idx
    state.frame_shape = frame.shape

    return ToolResult(
        success=True,
        data={"frame_idx": frame_idx, "shape": frame.shape},
        message=f"Reference frame: idx={frame_idx}, shape={frame.shape}",
        debug_artifacts={"reference_frame": frame},
    )
