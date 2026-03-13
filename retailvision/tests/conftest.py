"""Shared test fixtures for RetailVision test suite."""

import sqlite3
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

from agent.config import PipelineConfig
from agent.models import DwellPoint, FusedZone, ZoneCandidate
from agent.state import AgentState


# ── Paths ──

@pytest.fixture
def tmp_dir(tmp_path):
    """Temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database with schema initialized."""
    from tracker.database import TrackDatabase
    db_path = tmp_path / "test.db"
    db = TrackDatabase(db_path)
    yield db
    db.close()


# ── Config ──

@pytest.fixture
def config(tmp_path):
    """PipelineConfig with no API keys (offline mode)."""
    return PipelineConfig(
        db_path=tmp_path / "test.db",
        video_id="test_v1",
        output_dir=tmp_path / "output",
        openrouter_api_key="",
        replicate_api_token="",
        quality_threshold=0.30,
    )


# ── State Fixtures ──

@pytest.fixture
def empty_state():
    """Fresh AgentState."""
    return AgentState()


@pytest.fixture
def calibrated_state():
    """AgentState with calibrated tracks (BEV columns present)."""
    state = AgentState()
    state.video_id = "test_v1"
    state.video_duration_seconds = 1800.0
    state.frame_shape = (1080, 1920, 3)
    state.reference_frame = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    state.reference_frame_idx = 450

    # Homography (simple scaling: 0.05 m/px)
    state.bev_scale = 0.05
    state.bev_size = (96, 54)  # ~96m x 54m at 0.05 m/px
    state.homography_matrix = np.array([
        [0.05, 0, 0],
        [0, 0.05, 0],
        [0, 0, 1],
    ], dtype=np.float64)
    state.calibration_method = "person_height"
    state.scene_type = "indoor_food_court"

    # Build tracks DataFrame with BEV columns
    state.raw_tracks = _make_synthetic_tracks()
    return state


@pytest.fixture
def discovered_state(calibrated_state):
    """State with fused zones and dwell points."""
    state = calibrated_state

    # Dwell points
    state.dwell_points = [
        DwellPoint(track_id=1, centroid_bev=[10, 6], duration_seconds=120,
                   confinement_radius_m=1.2, start_frame=100, end_frame=3700, curvature=3.0),
        DwellPoint(track_id=2, centroid_bev=[10.5, 5.5], duration_seconds=90,
                   confinement_radius_m=0.8, start_frame=200, end_frame=2900, curvature=2.5),
        DwellPoint(track_id=3, centroid_bev=[30, 25], duration_seconds=200,
                   confinement_radius_m=1.5, start_frame=50, end_frame=6050, curvature=5.0),
        DwellPoint(track_id=4, centroid_bev=[31, 26], duration_seconds=180,
                   confinement_radius_m=1.0, start_frame=300, end_frame=5700, curvature=4.5),
        DwellPoint(track_id=5, centroid_bev=[50, 8], duration_seconds=240,
                   confinement_radius_m=1.8, start_frame=100, end_frame=7300, curvature=6.0),
    ]

    # Fused zones
    state.fused_zones = [
        FusedZone(
            zone_id="zone_001",
            polygon_bev=[[5, 2], [15, 2], [15, 10], [5, 10]],
            centroid_bev=[10, 6],
            area_m2=80,
            bbox_pixel=[100, 40, 300, 200],
            strategy_agreement=3,
            contributing_strategies=["dwell_clustering", "occupancy_grid", "trajectory_graph"],
        ),
        FusedZone(
            zone_id="zone_002",
            polygon_bev=[[20, 18], [40, 18], [40, 35], [20, 35]],
            centroid_bev=[30, 26.5],
            area_m2=340,
            bbox_pixel=[400, 360, 800, 700],
            strategy_agreement=2,
            contributing_strategies=["dwell_clustering", "occupancy_grid"],
        ),
        FusedZone(
            zone_id="zone_003",
            polygon_bev=[[45, 3], [55, 3], [55, 13], [45, 13]],
            centroid_bev=[50, 8],
            area_m2=100,
            bbox_pixel=[900, 60, 1100, 260],
            strategy_agreement=2,
            contributing_strategies=["occupancy_grid", "trajectory_graph"],
        ),
    ]

    state.fused_zones_dict = {z.zone_id: z for z in state.fused_zones}

    # Zone enrichment stubs (what VLM tools would produce)
    state.zone_crops = {}
    state.zone_classifications = {
        "zone_001": {"zone_type": "fast_food", "confidence": 0.85, "suggested_name": "Fast Food A"},
        "zone_002": {"zone_type": "seating_area", "confidence": 0.75, "suggested_name": "Seating Area"},
        "zone_003": {"zone_type": "cafe", "confidence": 0.80, "suggested_name": "Cafe"},
    }
    state.zone_signage = {
        "zone_001": {"primary_business_name": "Subway", "text_elements": [{"text": "SUBWAY"}]},
        "zone_002": {},
        "zone_003": {"primary_business_name": "Starbucks", "text_elements": [{"text": "STARBUCKS"}]},
    }
    state.zone_objects = {
        "zone_001": [{"name": "counter", "count": 1}],
        "zone_002": [{"name": "table", "count": 10}, {"name": "chair", "count": 30}],
        "zone_003": [{"name": "espresso_machine", "count": 1}],
    }
    state.zone_descriptions = {
        "zone_001": "Fast food counter",
        "zone_002": "Central seating area",
        "zone_003": "Coffee shop",
    }
    state.zone_depth_info = {
        "zone_001": {"width_estimate_m": 10, "depth_estimate_m": 8},
        "zone_002": {"width_estimate_m": 20, "depth_estimate_m": 17},
        "zone_003": {"width_estimate_m": 10, "depth_estimate_m": 10},
    }
    state.static_structures = []

    return state


# ── Helpers ──

def _make_synthetic_tracks(n_tracks=20, fps=30.0) -> pd.DataFrame:
    """Build a small synthetic DataFrame with BEV-calibrated tracks."""
    rng = np.random.default_rng(42)
    rows = []

    for tid in range(1, n_tracks + 1):
        n_frames = rng.integers(100, 600)
        # Random walk in BEV space
        bev_x = np.cumsum(rng.normal(0, 0.1, n_frames)) + rng.uniform(5, 55)
        bev_y = np.cumsum(rng.normal(0, 0.1, n_frames)) + rng.uniform(5, 45)
        timestamps = np.arange(n_frames) / fps + rng.uniform(0, 1800)

        for i in range(n_frames):
            px = bev_x[i] / 0.05  # BEV→pixel (simple scaling)
            py = bev_y[i] / 0.05
            rows.append({
                "video_id": "test_v1",
                "frame_idx": int(timestamps[i] * fps),
                "timestamp": timestamps[i],
                "track_id": tid,
                "x_center": px,
                "y_center": py,
                "bbox_x1": px - 15,
                "bbox_y1": py - 50,
                "bbox_x2": px + 15,
                "bbox_y2": py + 50,
                "bbox_w": 30.0,
                "bbox_h": 100.0,
                "confidence": 0.7 + rng.random() * 0.25,
                "object_class": "person",
                "bev_x_meters": bev_x[i],
                "bev_y_meters": bev_y[i],
                "speed_m_s": abs(rng.normal(0.5, 0.3)),
            })

    df = pd.DataFrame(rows)
    # Add time delta column
    df = df.sort_values(["track_id", "frame_idx"])
    df["dt"] = df.groupby("track_id")["timestamp"].diff().fillna(1 / fps)
    return df
