"""Test quick analytics for providing behavioral data before classification."""
import numpy as np
import pandas as pd
from agent.config import PipelineConfig
from agent.state import AgentState
from agent.tools.phase3_quick_analytics import compute_quick_zone_analytics


def _make_state_with_zones():
    state = AgentState()
    state.fused_zones_dict = {
        "zone_001": {
            "polygon_bev": [[0, 0], [2, 0], [2, 2], [0, 2]],
            "centroid_bev": [1, 1],
            "area_m2": 4.0,
        }
    }
    state.raw_tracks = pd.DataFrame({
        "track_id": [1, 1, 1, 2, 2],
        "bev_x_meters": [0.5, 1.0, 1.5, 0.8, 1.2],
        "bev_y_meters": [0.5, 1.0, 1.5, 0.8, 1.2],
        "timestamp": [0, 5, 10, 20, 25],
        "frame_idx": [0, 10, 20, 40, 50],
        "speed_m_s": [0.1, 0.1, 0.1, 0.2, 0.2],
    })
    state.video_duration_seconds = 60.0
    return state


def test_quick_analytics_produces_behavioral_data():
    state = _make_state_with_zones()
    config = PipelineConfig()
    result = compute_quick_zone_analytics(state, config)
    assert result.success
    assert "zone_001" in state.quick_zone_analytics
    analytics = state.quick_zone_analytics["zone_001"]
    assert "total_visits" in analytics
    assert "avg_dwell_seconds" in analytics
    assert "visits_per_hour" in analytics


def test_quick_analytics_empty_zones():
    state = AgentState()
    state.fused_zones_dict = {}
    state.raw_tracks = pd.DataFrame()
    config = PipelineConfig()
    result = compute_quick_zone_analytics(state, config)
    assert result.success
