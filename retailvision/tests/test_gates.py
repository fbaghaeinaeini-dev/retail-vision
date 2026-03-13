"""Test decision gates with mocked LLM responses."""
from agent.config import PipelineConfig
from agent.gates import (
    _clamp,
    apply_gate1_decision,
    apply_gate2_decision,
    apply_gate3_decision,
)
from agent.state import AgentState


def test_clamp():
    assert _clamp(5.0, 0.0, 10.0) == 5.0
    assert _clamp(-1.0, 0.0, 10.0) == 0.0
    assert _clamp(15.0, 0.0, 10.0) == 10.0


def test_apply_gate1_sets_profile():
    state = AgentState()
    config = PipelineConfig()
    decision = {
        "strategy_profile": "high_traffic",
        "parameters": {"min_dwell_seconds": 5.0, "stdbscan_spatial_eps_m": 3.0},
        "skip_tools": ["vlm_signage_reader"],
    }
    apply_gate1_decision(decision, state, config)

    assert state.strategy_profile == "high_traffic"
    assert config.min_dwell_seconds == 5.0
    assert config.stdbscan_spatial_eps_m == 3.0
    assert "vlm_signage_reader" not in state.active_phase3_tools


def test_apply_gate1_clamps_extreme_values():
    state = AgentState()
    config = PipelineConfig()
    decision = {
        "strategy_profile": "general",
        "parameters": {"min_dwell_seconds": 999.0},
        "skip_tools": [],
    }
    apply_gate1_decision(decision, state, config)
    assert config.min_dwell_seconds == 120.0


def test_apply_gate2_accept():
    state = AgentState()
    config = PipelineConfig()
    decision = {"accept": True, "issues": []}
    rerun = apply_gate2_decision(decision, state, config)
    assert rerun is False


def test_apply_gate2_rerun():
    state = AgentState()
    config = PipelineConfig()
    decision = {
        "accept": False,
        "rerun_with_adjustments": {"stdbscan_spatial_eps_m": 4.0},
    }
    rerun = apply_gate2_decision(decision, state, config)
    assert rerun is True
    assert state.phase2_retry_count == 1
    assert config.stdbscan_spatial_eps_m == 4.0


def test_apply_gate2_max_retries():
    state = AgentState()
    state.phase2_retry_count = 2
    config = PipelineConfig()
    decision = {"accept": False, "rerun_with_adjustments": {"stdbscan_spatial_eps_m": 4.0}}
    rerun = apply_gate2_decision(decision, state, config)
    assert rerun is False


def test_apply_gate3_reclassify():
    state = AgentState()
    state.zone_registry = {
        "zone_001": {"zone_type": "dining_area", "vlm_confidence": 0.3},
    }
    decision = {
        "accept": False,
        "reclassify": [
            {"zone_id": "zone_001", "new_type": "corridor", "reason": "misclassified"}
        ],
    }
    apply_gate3_decision(decision, state)
    assert state.zone_registry["zone_001"]["zone_type"] == "corridor"
    assert state.zone_registry["zone_001"]["reclassified_from"] == "dining_area"
