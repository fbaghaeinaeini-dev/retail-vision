"""Test PipelineConfig defaults and validation."""
from agent.config import PipelineConfig


def test_config_defaults():
    cfg = PipelineConfig()
    assert cfg.vlm_primary_model == "qwen/qwen3.5-35b-a3b"
    assert cfg.vlm_fallback_model == "qwen/qwen2.5-vl-7b-instruct"
    assert cfg.vlm_primary_model != cfg.vlm_fallback_model


def test_fusion_params_in_config():
    cfg = PipelineConfig()
    assert cfg.merge_threshold_m2 == 2.5
    assert cfg.merge_max_distance_m == 4.0
    assert cfg.max_zone_area_m2 == 50.0


def test_config_override():
    cfg = PipelineConfig(max_zone_area_m2=100.0, merge_threshold_m2=5.0)
    assert cfg.max_zone_area_m2 == 100.0
    assert cfg.merge_threshold_m2 == 5.0
