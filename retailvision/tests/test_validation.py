"""Tests for Phase 5: validation and quality gate."""

import pytest

from agent.config import PipelineConfig
from agent.tools.phase5_validate import validate_zones, _compute_coverage


class TestValidation:
    """Test zone validation metrics."""

    def test_validate_discovered_zones(self, discovered_state, config):
        """Merge zones first, then validate."""
        from agent.tools.phase3_merge import merge_zone_registry
        merge_zone_registry(discovered_state, config)

        result = validate_zones(discovered_state, config)
        assert result.success

        metrics = discovered_state.validation_metrics
        assert "overall_score" in metrics
        assert "silhouette" in metrics
        assert "coverage_pct" in metrics
        assert "vlm_agreement" in metrics
        assert "count_sanity" in metrics
        assert 0 <= metrics["overall_score"] <= 1

    def test_validate_empty_registry(self, empty_state, config):
        result = validate_zones(empty_state, config)
        assert result.success
        assert empty_state.validation_metrics["overall_score"] == 0

    def test_coverage_with_zones(self, discovered_state, config):
        from agent.tools.phase3_merge import merge_zone_registry
        merge_zone_registry(discovered_state, config)
        cov = _compute_coverage(discovered_state)
        assert 0 <= cov <= 1


class TestQualityGate:
    """Test quality gate pass/fail logic."""

    def test_passes_when_score_above_threshold(self, discovered_state, config):
        from agent.tools.phase3_merge import merge_zone_registry
        from agent.tools.phase5_validate import quality_gate

        merge_zone_registry(discovered_state, config)
        discovered_state.validation_metrics = {"overall_score": 0.80}
        config.quality_threshold = 0.40

        result = quality_gate(discovered_state, config)
        assert result.success
        assert result.data["passed"] is True
        assert discovered_state.quality_passed is True

    def test_fails_and_triggers_retry(self, discovered_state, config):
        from agent.tools.phase5_validate import quality_gate

        discovered_state.validation_metrics = {"overall_score": 0.10}
        discovered_state.phase2_retry_count = 0
        config.quality_threshold = 0.40

        result = quality_gate(discovered_state, config)
        assert result.data["passed"] is False
        assert result.data["retry"] is True

    def test_accepts_after_max_retries(self, discovered_state, config):
        from agent.tools.phase5_validate import quality_gate

        discovered_state.validation_metrics = {"overall_score": 0.10}
        discovered_state.phase2_retry_count = 2  # Max retries used
        config.quality_threshold = 0.40

        result = quality_gate(discovered_state, config)
        assert result.data["passed"] is False
        assert result.data["retry"] is False
        assert discovered_state.quality_passed is True  # Accepted despite fail
