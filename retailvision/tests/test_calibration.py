"""Tests for Phase 1: calibration and scene understanding."""

import numpy as np
import pandas as pd
import pytest

from agent.models import ToolResult
from agent.state import AgentState
from agent.config import PipelineConfig


class TestCalibration:
    """Test person-height regression calibration."""

    def test_fallback_when_insufficient_data(self, config):
        """With very few tracks, should fall back to simple scaling."""
        state = AgentState()
        state.video_id = "test_v1"
        state.frame_shape = (1080, 1920, 3)

        # Minimal tracks with only 1 y-bin
        rows = []
        for i in range(10):
            rows.append({
                "video_id": "test_v1", "frame_idx": i, "timestamp": i / 30.0,
                "track_id": 1, "x_center": 960.0, "y_center": 540.0,
                "bbox_x1": 940.0, "bbox_y1": 490.0, "bbox_x2": 980.0, "bbox_y2": 590.0,
                "bbox_w": 40.0, "bbox_h": 100.0, "confidence": 0.8, "object_class": "person",
            })
        df = pd.DataFrame(rows)
        df = df.sort_values(["track_id", "frame_idx"])
        df["dt"] = df.groupby("track_id")["timestamp"].diff().fillna(1 / 30.0)
        state.raw_tracks = df

        from agent.tools.phase1_calibrate import calibrate_from_person_height
        result = calibrate_from_person_height(state, config)

        assert result.success
        assert state.homography_matrix is not None
        assert state.bev_scale > 0

    def test_calibration_produces_bev_columns(self, config):
        """After calibration, tracks should have bev_x_meters and bev_y_meters."""
        state = AgentState()
        state.video_id = "test_v1"
        state.frame_shape = (1080, 1920, 3)

        # Create tracks with perspective variation
        rng = np.random.default_rng(42)
        rows = []
        for tid in range(1, 20):
            y_pos = rng.uniform(200, 900)
            # Simulate perspective: larger bbox_h when y is larger (closer to camera)
            bbox_h = 1.7 * 800 / (y_pos + 500)
            for i in range(30):
                x = 960 + rng.normal(0, 50)
                y = y_pos + rng.normal(0, 10)
                rows.append({
                    "video_id": "test_v1", "frame_idx": tid * 100 + i,
                    "timestamp": (tid * 100 + i) / 30.0,
                    "track_id": tid, "x_center": x, "y_center": y,
                    "bbox_x1": x - 15, "bbox_y1": y - bbox_h / 2,
                    "bbox_x2": x + 15, "bbox_y2": y + bbox_h / 2,
                    "bbox_w": 30.0, "bbox_h": bbox_h,
                    "confidence": 0.85, "object_class": "person",
                })
        df = pd.DataFrame(rows)
        df = df.sort_values(["track_id", "frame_idx"])
        df["dt"] = df.groupby("track_id")["timestamp"].diff().fillna(1 / 30.0)
        state.raw_tracks = df

        from agent.tools.phase1_calibrate import calibrate_from_person_height
        result = calibrate_from_person_height(state, config)

        assert result.success
        assert "bev_x_meters" in state.raw_tracks.columns
        assert "bev_y_meters" in state.raw_tracks.columns
        assert "speed_m_s" in state.raw_tracks.columns


class TestSceneClassification:
    """Test heuristic scene classifier."""

    def test_classify_from_tracks(self, calibrated_state, config):
        from agent.tools.phase1_scene import classify_scene_type
        result = classify_scene_type(calibrated_state, config)

        assert result.success
        assert calibrated_state.scene_type in [
            "indoor_food_court", "indoor_mall", "outdoor_plaza", "corridor", "unknown"
        ]

    def test_gate1_applies_params(self, config):
        """Gate 1 should apply LLM-chosen params to config."""
        from agent.gates import apply_gate1_decision
        from agent.state import AgentState
        state = AgentState()
        decision = {
            "strategy_profile": "pedestrian_indoor",
            "parameters": {"stdbscan_spatial_eps_m": 1.5, "min_dwell_seconds": 15.0},
            "skip_tools": [],
        }
        apply_gate1_decision(decision, state, config)
        assert config.stdbscan_spatial_eps_m == 1.5
        assert config.min_dwell_seconds == 15.0

    def test_unknown_profile_uses_general_tools(self, config):
        """Unknown profile should fall back to general profile's tools."""
        from agent.gates import apply_gate1_decision
        from agent.strategy_profiles import get_profile
        from agent.state import AgentState
        state = AgentState()
        original_eps = config.stdbscan_spatial_eps_m
        decision = {
            "strategy_profile": "alien_spaceship",
            "parameters": {},
            "skip_tools": [],
        }
        apply_gate1_decision(decision, state, config)
        assert config.stdbscan_spatial_eps_m == original_eps
        # get_profile falls back to general, so tools should match
        general = get_profile("general")
        assert state.active_phase2_tools == general["phase2_tools"]
