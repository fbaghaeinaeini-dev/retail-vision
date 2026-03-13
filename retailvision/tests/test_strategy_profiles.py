"""Test strategy profile selection."""
from agent.strategy_profiles import STRATEGY_PROFILES, get_profile, get_profile_names


def test_all_profiles_have_required_keys():
    for name, profile in STRATEGY_PROFILES.items():
        assert "description" in profile
        assert "phase2_tools" in profile
        assert "phase3_tools" in profile
        assert "fuse_zone_candidates" in profile["phase2_tools"]
        assert "merge_zone_registry" in profile["phase3_tools"]


def test_get_profile_valid():
    profile = get_profile("pedestrian_indoor")
    assert profile is not None
    assert "compute_dwell_points" in profile["phase2_tools"]


def test_get_profile_fallback():
    profile = get_profile("nonexistent_profile")
    assert profile is not None
    assert profile == STRATEGY_PROFILES["general"]


def test_profile_names():
    names = get_profile_names()
    assert "general" in names
    assert "pedestrian_indoor" in names
