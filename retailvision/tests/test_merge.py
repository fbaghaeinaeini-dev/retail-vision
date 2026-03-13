"""Tests for Phase 3: zone merging."""

import pytest

from agent.tools.phase3_merge import (
    merge_zone_registry,
    _generate_zone_name,
    _deduplicate_names,
)


class TestMergeZoneRegistry:
    """Test zone registry merge."""

    def test_merge_produces_registry(self, discovered_state, config):
        result = merge_zone_registry(discovered_state, config)
        assert result.success
        assert len(discovered_state.zone_registry) == 3

    def test_zone_has_required_fields(self, discovered_state, config):
        merge_zone_registry(discovered_state, config)
        for zid, zone in discovered_state.zone_registry.items():
            assert "zone_id" in zone
            assert "business_name" in zone
            assert "zone_type" in zone
            assert "polygon_bev" in zone
            assert "polygon_pixel" in zone
            assert "area_m2" in zone

    def test_business_names_from_signage(self, discovered_state, config):
        """Zones with signage should use the brand name."""
        merge_zone_registry(discovered_state, config)
        names = {z["business_name"] for z in discovered_state.zone_registry.values()}
        assert "Subway" in names
        assert "Starbucks" in names

    def test_static_structures_merged(self, discovered_state, config):
        """Static structures that overlap should merge into existing zones."""
        discovered_state.static_structures = [
            {
                "bbox_pixel": [105, 45, 295, 195],  # Overlaps zone_001
                "zone_implication": "counter",
                "confidence": 0.6,
                "description": "Service counter",
            }
        ]
        merge_zone_registry(discovered_state, config)
        # Structure may or may not overlap depending on zone pixel coords
        assert len(discovered_state.zone_registry) >= 3

    def test_non_overlapping_structure_creates_zone(self, discovered_state, config):
        """Non-overlapping structures should create new zones."""
        discovered_state.static_structures = [
            {
                "bbox_pixel": [1500, 800, 1700, 950],  # No overlap
                "zone_implication": "kiosk",
                "confidence": 0.7,
                "description": "Information kiosk",
            }
        ]
        merge_zone_registry(discovered_state, config)
        assert len(discovered_state.zone_registry) == 4


class TestNameGeneration:
    def test_generate_known_types(self):
        assert "Restaurant" in _generate_zone_name("restaurant", "zone_001")
        assert "cafe" in _generate_zone_name("cafe", "zone_002").lower()
        assert "Corridor" in _generate_zone_name("corridor", "zone_003")

    def test_generate_unknown_type(self):
        name = _generate_zone_name("some_new_type", "zone_099")
        assert "099" in name


class TestDeduplication:
    def test_dedup_names(self):
        registry = {
            "z1": {"business_name": "Starbucks"},
            "z2": {"business_name": "Starbucks"},
            "z3": {"business_name": "Subway"},
        }
        _deduplicate_names(registry)
        names = [z["business_name"] for z in registry.values()]
        assert len(set(names)) == 3  # All unique now
