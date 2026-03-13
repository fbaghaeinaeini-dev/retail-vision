"""Tests for the data query tools module."""

import pytest

from api.data_tools import (
    get_flow_data,
    get_full_data_context,
    get_summary_stats,
    get_top_zones,
    get_zone_detail,
    query_zones,
    search_zones_by_name,
)


# ── Shared fixtures ──────────────────────────────────────────

@pytest.fixture()
def sample_report() -> dict:
    """A minimal but complete report for testing data tools."""
    return {
        "meta": {
            "video_id": "test_vid",
            "scene_type": "indoor_food_court",
            "duration_seconds": 900.0,
        },
        "zones": {
            "zone_001": {
                "zone_id": "zone_001",
                "business_name": "Test Cafe",
                "zone_type": "cafe",
                "vlm_confidence": 0.85,
                "description": "A cozy cafe with espresso machines.",
                "polygon_bev": [[1.0, 2.0], [3.0, 2.0], [3.0, 4.0], [1.0, 4.0]],
                "polygon_pixel": [[100, 200], [300, 200], [300, 400], [100, 400]],
                "centroid_bev": [2.0, 3.0],
                "area_m2": 25.0,
                "bbox_pixel": [100, 200, 300, 400],
                "depth_info": {"width_estimate_m": 5, "depth_estimate_m": 5},
                "objects": [{"name": "espresso_machine", "count": 1}],
                "signage": {"primary_business_name": "Test Cafe"},
                "strategy_agreement": 3,
                "contributing_strategies": ["dwell", "occupancy", "trajectory"],
            },
            "zone_002": {
                "zone_id": "zone_002",
                "business_name": "Test Seating",
                "zone_type": "seating_area",
                "vlm_confidence": 0.75,
                "description": "Large seating area with tables.",
                "polygon_bev": [[5.0, 2.0], [10.0, 2.0], [10.0, 6.0], [5.0, 6.0]],
                "polygon_pixel": [[500, 200], [1000, 200], [1000, 600], [500, 600]],
                "centroid_bev": [7.5, 4.0],
                "area_m2": 100.0,
                "bbox_pixel": [500, 200, 1000, 600],
                "depth_info": {},
                "objects": [],
                "signage": {},
                "strategy_agreement": 2,
                "contributing_strategies": ["dwell", "occupancy"],
            },
            "zone_003": {
                "zone_id": "zone_003",
                "business_name": "Xiaomi Kiosk",
                "zone_type": "kiosk",
                "vlm_confidence": 0.9,
                "description": "Electronics kiosk.",
                "polygon_bev": [[12.0, 1.0], [15.0, 1.0], [15.0, 3.0], [12.0, 3.0]],
                "polygon_pixel": [[1200, 100], [1500, 100], [1500, 300], [1200, 300]],
                "centroid_bev": [13.5, 2.0],
                "area_m2": 18.0,
                "bbox_pixel": [1200, 100, 1500, 300],
                "depth_info": {},
                "objects": [],
                "signage": {},
                "strategy_agreement": 2,
                "contributing_strategies": ["occupancy", "trajectory"],
            },
        },
        "analytics": {
            "zone_001": {
                "total_visits": 120,
                "unique_visitors": 110,
                "avg_dwell_seconds": 30.5,
                "median_dwell_seconds": 25.0,
                "p95_dwell_seconds": 60.0,
                "peak_hour": 12,
                "hourly_visits": {"12": 50, "13": 40, "14": 30},
                "avg_occupancy": 5.0,
                "max_occupancy": 15,
                "return_rate": 0.05,
                "density_people_per_m2_hr": 4.8,
            },
            "zone_002": {
                "total_visits": 80,
                "unique_visitors": 75,
                "avg_dwell_seconds": 90.0,
                "median_dwell_seconds": 80.0,
                "p95_dwell_seconds": 180.0,
                "peak_hour": 13,
                "hourly_visits": {"12": 20, "13": 35, "14": 25},
                "avg_occupancy": 10.0,
                "max_occupancy": 25,
                "return_rate": 0.10,
                "density_people_per_m2_hr": 0.8,
            },
            "zone_003": {
                "total_visits": 200,
                "unique_visitors": 190,
                "avg_dwell_seconds": 15.0,
                "median_dwell_seconds": 10.0,
                "p95_dwell_seconds": 40.0,
                "peak_hour": 14,
                "hourly_visits": {"12": 60, "13": 70, "14": 70},
                "avg_occupancy": 3.0,
                "max_occupancy": 12,
                "return_rate": 0.02,
                "density_people_per_m2_hr": 11.1,
            },
        },
        "flow": {
            "transitions": [
                {"from_zone": "zone_001", "to_zone": "zone_002", "count": 42, "probability": 0.35, "avg_travel_seconds": 5},
                {"from_zone": "zone_002", "to_zone": "zone_003", "count": 30, "probability": 0.38, "avg_travel_seconds": 8},
                {"from_zone": "zone_003", "to_zone": "zone_001", "count": 25, "probability": 0.13, "avg_travel_seconds": 10},
            ],
            "top_paths": [
                {"from_zone": "zone_001", "to_zone": "zone_002", "count": 42},
                {"from_zone": "zone_002", "to_zone": "zone_003", "count": 30},
            ],
        },
        "temporal": {
            "time_bin_seconds": 300,
            "occupancy_matrix": {
                "zone_001": [100, 200, 300, 250, 150, 100],
                "zone_002": [50, 80, 120, 90, 70, 60],
                "zone_003": [400, 500, 350, 300, 200, 150],
            },
        },
    }


# ── query_zones ──────────────────────────────────────────────

class TestQueryZones:
    def test_default_sort_by_visits_desc(self, sample_report):
        result = query_zones(sample_report)
        assert len(result) == 3
        assert result[0]["zone_id"] == "zone_003"  # 200 visits
        assert result[1]["zone_id"] == "zone_001"  # 120 visits
        assert result[2]["zone_id"] == "zone_002"  # 80 visits

    def test_sort_by_dwell_desc(self, sample_report):
        result = query_zones(sample_report, sort_by="avg_dwell_seconds")
        assert result[0]["zone_id"] == "zone_002"  # 90s
        assert result[1]["zone_id"] == "zone_001"  # 30.5s

    def test_sort_asc(self, sample_report):
        result = query_zones(sample_report, sort_by="total_visits", order="asc")
        assert result[0]["zone_id"] == "zone_002"  # 80
        assert result[-1]["zone_id"] == "zone_003"  # 200

    def test_limit(self, sample_report):
        result = query_zones(sample_report, limit=2)
        assert len(result) == 2

    def test_filter_by_zone_type(self, sample_report):
        result = query_zones(sample_report, zone_type="cafe")
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_001"

    def test_filter_by_zone_type_no_match(self, sample_report):
        result = query_zones(sample_report, zone_type="restaurant")
        assert len(result) == 0

    def test_all_metrics_present(self, sample_report):
        result = query_zones(sample_report)
        z = result[0]
        assert "total_visits" in z
        assert "avg_dwell_seconds" in z
        assert "density_people_per_m2_hr" in z
        assert "name" in z
        assert "zone_type" in z

    def test_human_metric_alias(self, sample_report):
        result = query_zones(sample_report, sort_by="dwell")
        assert result[0]["zone_id"] == "zone_002"  # highest dwell


# ── get_top_zones ────────────────────────────────────────────

class TestGetTopZones:
    def test_top_2_by_visits(self, sample_report):
        result = get_top_zones(sample_report, "total_visits", n=2)
        assert len(result) == 2
        assert result[0]["zone_id"] == "zone_003"
        assert result[0]["value"] == 200
        assert result[0]["label"] == "Xiaomi Kiosk"

    def test_top_by_dwell(self, sample_report):
        result = get_top_zones(sample_report, "dwell", n=1)
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_002"
        assert result[0]["value"] == 90.0

    def test_top_by_density(self, sample_report):
        result = get_top_zones(sample_report, "density", n=2)
        assert result[0]["zone_id"] == "zone_003"  # 11.1
        assert result[1]["zone_id"] == "zone_001"  # 4.8


# ── get_zone_detail ──────────────────────────────────────────

class TestGetZoneDetail:
    def test_returns_full_detail(self, sample_report):
        detail = get_zone_detail(sample_report, "zone_001")
        assert detail is not None
        assert detail["name"] == "Test Cafe"
        assert detail["zone_type"] == "cafe"
        assert detail["description"] == "A cozy cafe with espresso machines."
        assert len(detail["polygon_bev"]) == 4
        assert len(detail["polygon_pixel"]) == 4
        assert detail["bbox_pixel"] == [100, 200, 300, 400]
        assert detail["total_visits"] == 120
        assert detail["avg_dwell_seconds"] == 30.5
        assert detail["area_m2"] == 25.0

    def test_returns_none_for_missing(self, sample_report):
        assert get_zone_detail(sample_report, "zone_999") is None


# ── search_zones_by_name ─────────────────────────────────────

class TestSearchZonesByName:
    def test_finds_cafe(self, sample_report):
        result = search_zones_by_name(sample_report, "cafe")
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_001"

    def test_finds_xiaomi(self, sample_report):
        result = search_zones_by_name(sample_report, "xiaomi")
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_003"

    def test_case_insensitive(self, sample_report):
        result = search_zones_by_name(sample_report, "TEST")
        assert len(result) == 2  # Test Cafe, Test Seating

    def test_no_match(self, sample_report):
        result = search_zones_by_name(sample_report, "subway")
        assert len(result) == 0


# ── get_flow_data ────────────────────────────────────────────

class TestGetFlowData:
    def test_all_transitions(self, sample_report):
        flow = get_flow_data(sample_report)
        assert len(flow["transitions"]) == 3
        assert len(flow["top_paths"]) == 2

    def test_filtered_by_zone(self, sample_report):
        flow = get_flow_data(sample_report, "zone_001")
        # zone_001 -> zone_002 (from), zone_003 -> zone_001 (to)
        assert len(flow["transitions"]) == 2
        zones_involved = set()
        for t in flow["transitions"]:
            zones_involved.add(t["from_zone"])
            zones_involved.add(t["to_zone"])
        assert "zone_001" in zones_involved

    def test_filtered_no_match(self, sample_report):
        flow = get_flow_data(sample_report, "zone_999")
        assert len(flow["transitions"]) == 0


# ── get_summary_stats ────────────────────────────────────────

class TestGetSummaryStats:
    def test_summary(self, sample_report):
        stats = get_summary_stats(sample_report)
        assert stats["total_zones"] == 3
        assert stats["total_visits"] == 400  # 120 + 80 + 200
        assert stats["busiest_zone_id"] == "zone_003"
        assert stats["busiest_zone_name"] == "Xiaomi Kiosk"
        assert stats["busiest_zone_visits"] == 200
        assert "cafe" in stats["zone_type_counts"]
        assert stats["avg_dwell"] > 0


# ── get_full_data_context ────────────────────────────────────

class TestGetFullDataContext:
    def test_includes_all_zones(self, sample_report):
        ctx = get_full_data_context(sample_report)
        assert "zone_001" in ctx
        assert "zone_002" in ctx
        assert "zone_003" in ctx
        assert "Test Cafe" in ctx
        assert "Xiaomi Kiosk" in ctx

    def test_includes_summary_stats(self, sample_report):
        ctx = get_full_data_context(sample_report)
        assert "400 total visits" in ctx
        assert "busiest zone" in ctx.lower() or "Xiaomi Kiosk" in ctx

    def test_includes_flow(self, sample_report):
        ctx = get_full_data_context(sample_report)
        assert "Test Cafe" in ctx
        assert "Flow data available" in ctx

    def test_includes_video_start_time(self, sample_report):
        ctx = get_full_data_context(sample_report)
        assert "10:15:40" in ctx

    def test_includes_zone_types(self, sample_report):
        ctx = get_full_data_context(sample_report)
        assert "cafe" in ctx
        assert "kiosk" in ctx

    def test_empty_report(self):
        ctx = get_full_data_context({})
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ── Unknown zone name fallback ───────────────────────────────

class TestUnknownZoneLabel:
    def test_unknown_uses_description(self):
        from api.data_tools import _zone_label
        zone = {
            "business_name": "Unknown",
            "zone_type": "seating_area",
            "description": "This zone functions as a casual dining area featuring two long tables.",
        }
        label = _zone_label(zone)
        assert label != "Unknown"
        assert "dining" in label.lower() or "casual" in label.lower()

    def test_unknown_013_uses_description(self):
        from api.data_tools import _zone_label
        zone = {
            "business_name": "Unknown 013",
            "zone_type": "unknown",
            "description": "Sign for ATMs and restrooms",
        }
        label = _zone_label(zone)
        assert label != "Unknown 013"
        assert "atm" in label.lower() or "restroom" in label.lower()

    def test_normal_name_unchanged(self):
        from api.data_tools import _zone_label
        zone = {"business_name": "Xiaomi Kiosk", "zone_type": "kiosk"}
        assert _zone_label(zone) == "Xiaomi Kiosk"

    def test_no_name_no_desc_uses_type(self):
        from api.data_tools import _zone_label
        zone = {"zone_type": "cafe"}
        label = _zone_label(zone)
        assert label == "Cafe"

    def test_no_name_no_desc_no_type(self):
        from api.data_tools import _zone_label
        zone = {"zone_id": "zone_099"}
        label = _zone_label(zone)
        assert label == "zone_099"
