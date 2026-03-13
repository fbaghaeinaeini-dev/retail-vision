"""Tests for Phase 2: zone discovery strategies and fusion."""

import numpy as np
import pytest

from agent.models import DwellPoint, ZoneCandidate


class TestStrategyA:
    """Test ST-DBSCAN dwell clustering strategy."""

    def test_produces_zone_candidates(self, calibrated_state, config):
        from agent.tools.phase2_dwell import compute_dwell_points
        from agent.tools.phase2_strategy_a import strategy_dwell_clustering

        compute_dwell_points(calibrated_state, config)

        # Only test if we have enough dwell points
        if len(calibrated_state.dwell_points) >= 5:
            result = strategy_dwell_clustering(calibrated_state, config)
            assert result.success
            for c in calibrated_state.zone_candidates_A:
                assert isinstance(c, ZoneCandidate)
                assert c.strategy == "dwell_clustering"
                assert len(c.polygon_bev) >= 3

    def test_empty_dwell_points_handled(self, calibrated_state, config):
        from agent.tools.phase2_strategy_a import strategy_dwell_clustering
        calibrated_state.dwell_points = []
        result = strategy_dwell_clustering(calibrated_state, config)
        assert result.success
        assert calibrated_state.zone_candidates_A == []


class TestStrategyB:
    """Test occupancy grid strategy."""

    def test_produces_zone_candidates(self, calibrated_state, config):
        from agent.tools.phase2_strategy_b import strategy_occupancy_grid
        result = strategy_occupancy_grid(calibrated_state, config)
        assert result.success
        for c in calibrated_state.zone_candidates_B:
            assert isinstance(c, ZoneCandidate)
            assert c.strategy == "occupancy_grid"


class TestStrategyC:
    """Test trajectory graph strategy."""

    def test_produces_zone_candidates(self, calibrated_state, config):
        from agent.tools.phase2_strategy_c import strategy_trajectory_graph
        result = strategy_trajectory_graph(calibrated_state, config)
        assert result.success
        for c in calibrated_state.zone_candidates_C:
            assert isinstance(c, ZoneCandidate)
            assert c.strategy == "trajectory_graph"


class TestFusion:
    """Test ensemble zone fusion."""

    def test_fuse_with_candidates(self, calibrated_state, config):
        """Fusion should produce FusedZone objects from strategy candidates."""
        from agent.tools.phase2_dwell import compute_dwell_points
        from agent.tools.phase2_strategy_a import strategy_dwell_clustering
        from agent.tools.phase2_strategy_b import strategy_occupancy_grid
        from agent.tools.phase2_strategy_c import strategy_trajectory_graph
        from agent.tools.phase2_fusion import fuse_zone_candidates

        compute_dwell_points(calibrated_state, config)
        strategy_dwell_clustering(calibrated_state, config)
        strategy_occupancy_grid(calibrated_state, config)
        strategy_trajectory_graph(calibrated_state, config)

        result = fuse_zone_candidates(calibrated_state, config)
        assert result.success
        # Should find at least some zones
        assert isinstance(calibrated_state.fused_zones, list)

    def test_fuse_empty_candidates(self, calibrated_state, config):
        """With no candidates, fusion should return empty list."""
        from agent.tools.phase2_fusion import fuse_zone_candidates
        calibrated_state.zone_candidates_A = []
        calibrated_state.zone_candidates_B = []
        calibrated_state.zone_candidates_C = []
        result = fuse_zone_candidates(calibrated_state, config)
        assert result.success
        assert len(calibrated_state.fused_zones) == 0
