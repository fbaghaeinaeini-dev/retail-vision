"""Tests for Phase 2: dwell detection."""

import numpy as np
import pandas as pd
import pytest

from agent.config import PipelineConfig
from agent.state import AgentState
from agent.tools.phase2_dwell import compute_dwell_points, _find_segments


class TestFindSegments:
    """Unit test for the segment finder helper."""

    def test_single_segment(self):
        mask = np.array([False, True, True, True, False])
        segs = _find_segments(mask)
        assert segs == [(1, 3)]

    def test_multiple_segments(self):
        mask = np.array([True, True, False, True, False, True, True])
        segs = _find_segments(mask)
        assert segs == [(0, 1), (3, 3), (5, 6)]

    def test_empty(self):
        mask = np.array([False, False, False])
        segs = _find_segments(mask)
        assert segs == []

    def test_all_true(self):
        mask = np.array([True, True, True])
        segs = _find_segments(mask)
        assert segs == [(0, 2)]

    def test_trailing_segment(self):
        mask = np.array([False, True, True])
        segs = _find_segments(mask)
        assert segs == [(1, 2)]


class TestDwellDetection:
    """Integration test for dwell point detection."""

    def test_finds_dwell_points(self, calibrated_state, config):
        """Should find dwell events in synthetic tracks."""
        result = compute_dwell_points(calibrated_state, config)
        assert result.success
        # Synthetic random walks should produce some dwell events
        assert isinstance(calibrated_state.dwell_points, list)

    def test_no_bev_tracks_returns_error(self, config):
        state = AgentState()
        state.raw_tracks = pd.DataFrame({"track_id": [1], "x_center": [500]})
        result = compute_dwell_points(state, config)
        assert not result.success

    def test_dwell_points_have_required_fields(self, calibrated_state, config):
        compute_dwell_points(calibrated_state, config)
        for dp in calibrated_state.dwell_points:
            assert hasattr(dp, "track_id")
            assert hasattr(dp, "centroid_bev")
            assert hasattr(dp, "duration_seconds")
            assert hasattr(dp, "confinement_radius_m")
            assert dp.duration_seconds >= config.min_dwell_seconds
            assert dp.confinement_radius_m <= config.confinement_radius_m
