"""Tests for the agentic chat tool definitions and executor."""

import pytest

from api.chat_tools import TOOLS, execute_tool, get_tool_names


@pytest.fixture()
def sample_report() -> dict:
    """Minimal report for testing tool execution."""
    return {
        "meta": {"video_id": "test_vid", "scene_type": "indoor", "duration_seconds": 900},
        "zones": {
            "zone_001": {
                "zone_id": "zone_001",
                "business_name": "Test Cafe",
                "zone_type": "cafe",
                "description": "A cafe.",
                "polygon_bev": [[1, 2], [3, 2], [3, 4], [1, 4]],
                "polygon_pixel": [[100, 200], [300, 200], [300, 400], [100, 400]],
                "centroid_bev": [2, 3],
                "area_m2": 25.0,
                "bbox_pixel": [100, 200, 300, 400],
            },
            "zone_002": {
                "zone_id": "zone_002",
                "business_name": "Test Kiosk",
                "zone_type": "kiosk",
                "description": "A kiosk.",
                "polygon_bev": [[5, 2], [8, 2], [8, 4], [5, 4]],
                "polygon_pixel": [[500, 200], [800, 200], [800, 400], [500, 400]],
                "centroid_bev": [6.5, 3],
                "area_m2": 18.0,
                "bbox_pixel": [500, 200, 800, 400],
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
                "avg_occupancy": 5.0,
                "max_occupancy": 15,
                "return_rate": 0.05,
                "density_people_per_m2_hr": 4.8,
            },
            "zone_002": {
                "total_visits": 200,
                "unique_visitors": 190,
                "avg_dwell_seconds": 15.0,
                "median_dwell_seconds": 10.0,
                "p95_dwell_seconds": 40.0,
                "peak_hour": 14,
                "avg_occupancy": 3.0,
                "max_occupancy": 12,
                "return_rate": 0.02,
                "density_people_per_m2_hr": 11.1,
            },
        },
        "flow": {
            "transitions": [
                {"from_zone": "zone_001", "to_zone": "zone_002", "count": 42, "probability": 0.35},
            ],
            "top_paths": [
                {"from_zone": "zone_001", "to_zone": "zone_002", "count": 42},
            ],
        },
        "temporal": {"time_bin_seconds": 300, "occupancy_matrix": {}},
    }


class TestToolDefinitions:
    def test_all_tools_have_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["parameters"]["type"] == "object"

    def test_tool_names(self):
        names = get_tool_names()
        assert "query_zones" in names
        assert "get_zone_detail" in names
        assert "search_zones" in names
        assert "get_flow_data" in names
        assert "get_summary_stats" in names


class TestExecuteTool:
    def test_query_zones_default(self, sample_report):
        result = execute_tool("query_zones", {}, sample_report)
        assert isinstance(result, list)
        assert len(result) == 2
        # Default sort by visits desc → zone_002 first (200)
        assert result[0]["zone_id"] == "zone_002"

    def test_query_zones_with_limit(self, sample_report):
        result = execute_tool("query_zones", {"limit": 1}, sample_report)
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_002"

    def test_query_zones_sort_dwell(self, sample_report):
        result = execute_tool(
            "query_zones",
            {"sort_by": "avg_dwell_seconds", "order": "desc"},
            sample_report,
        )
        assert result[0]["zone_id"] == "zone_001"  # 30.5s > 15.0s

    def test_query_zones_filter_type(self, sample_report):
        result = execute_tool(
            "query_zones", {"zone_type": "cafe"}, sample_report
        )
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_001"

    def test_get_zone_detail(self, sample_report):
        result = execute_tool(
            "get_zone_detail", {"zone_id": "zone_001"}, sample_report
        )
        assert result["name"] == "Test Cafe"
        assert result["total_visits"] == 120
        assert "polygon_bev" in result

    def test_get_zone_detail_missing(self, sample_report):
        result = execute_tool(
            "get_zone_detail", {"zone_id": "zone_999"}, sample_report
        )
        assert "error" in result

    def test_search_zones(self, sample_report):
        result = execute_tool("search_zones", {"query": "cafe"}, sample_report)
        assert len(result) == 1
        assert result[0]["zone_id"] == "zone_001"

    def test_search_zones_no_match(self, sample_report):
        result = execute_tool("search_zones", {"query": "xyz"}, sample_report)
        assert len(result) == 0

    def test_get_flow_data_all(self, sample_report):
        result = execute_tool("get_flow_data", {}, sample_report)
        assert len(result["transitions"]) == 1
        assert result["transitions"][0]["count"] == 42

    def test_get_flow_data_filtered(self, sample_report):
        result = execute_tool(
            "get_flow_data", {"zone_id": "zone_001"}, sample_report
        )
        assert len(result["transitions"]) == 1

    def test_get_summary_stats(self, sample_report):
        result = execute_tool("get_summary_stats", {}, sample_report)
        assert result["total_zones"] == 2
        assert result["total_visits"] == 320
        assert result["busiest_zone_id"] == "zone_002"

    def test_unknown_tool(self, sample_report):
        result = execute_tool("nonexistent_tool", {}, sample_report)
        assert "error" in result
