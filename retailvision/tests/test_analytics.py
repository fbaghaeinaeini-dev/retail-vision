"""Tests for Phase 4: analytics tools."""

import pytest

from agent.tools.phase4_analytics import (
    compute_zone_analytics,
    compute_flow_analytics,
    compute_temporal_analytics,
    compute_spatial_analytics,
)


class TestZoneAnalytics:
    """Test per-zone analytics computation."""

    def test_compute_analytics(self, discovered_state, config):
        from agent.tools.phase3_merge import merge_zone_registry
        merge_zone_registry(discovered_state, config)

        result = compute_zone_analytics(discovered_state, config)
        assert result.success

    def test_empty_registry(self, calibrated_state, config):
        result = compute_zone_analytics(calibrated_state, config)
        assert result.success


class TestFlowAnalytics:
    def test_compute_flow(self, discovered_state, config):
        from agent.tools.phase3_merge import merge_zone_registry
        merge_zone_registry(discovered_state, config)

        result = compute_flow_analytics(discovered_state, config)
        assert result.success
        assert "transitions" in discovered_state.flow_analytics or discovered_state.flow_analytics == {}


class TestTemporalAnalytics:
    def test_compute_temporal(self, discovered_state, config):
        from agent.tools.phase3_merge import merge_zone_registry
        merge_zone_registry(discovered_state, config)

        result = compute_temporal_analytics(discovered_state, config)
        assert result.success


class TestSpatialAnalytics:
    def test_compute_spatial(self, calibrated_state, config):
        result = compute_spatial_analytics(calibrated_state, config)
        assert result.success

        if calibrated_state.spatial_analytics:
            assert "heatmap_density" in calibrated_state.spatial_analytics
            assert "cell_size_m" in calibrated_state.spatial_analytics

    def test_no_bev_columns(self, empty_state, config):
        import pandas as pd
        empty_state.raw_tracks = pd.DataFrame({"track_id": [1]})
        result = compute_spatial_analytics(empty_state, config)
        assert result.success
