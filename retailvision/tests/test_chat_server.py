"""Tests for the FastAPI chat server."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.chat_server import _parse_vlm_json, create_app


@pytest.fixture()
def mock_report(tmp_path: Path) -> Path:
    """Write a minimal report.json and return its path."""
    report = {
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
                "description": "A test cafe.",
                "polygon_bev": [[1, 2], [3, 2], [3, 4], [1, 4]],
                "polygon_pixel": [[100, 200], [300, 200], [300, 400], [100, 400]],
                "centroid_bev": [2, 3],
                "area_m2": 25.0,
                "bbox_pixel": [100, 200, 300, 400],
            },
            "zone_002": {
                "zone_id": "zone_002",
                "business_name": "Test Seating",
                "zone_type": "seating_area",
                "description": "A test seating area.",
                "polygon_bev": [[5, 2], [10, 2], [10, 6], [5, 6]],
                "polygon_pixel": [[500, 200], [1000, 200], [1000, 600], [500, 600]],
                "centroid_bev": [7.5, 4],
                "area_m2": 100.0,
                "bbox_pixel": [500, 200, 1000, 600],
            },
            "zone_003": {
                "zone_id": "zone_003",
                "business_name": "Test Kiosk",
                "zone_type": "kiosk",
                "description": "A test kiosk.",
                "polygon_bev": [[12, 1], [15, 1], [15, 3], [12, 3]],
                "polygon_pixel": [[1200, 100], [1500, 100], [1500, 300], [1200, 300]],
                "centroid_bev": [13.5, 2],
                "area_m2": 18.0,
                "bbox_pixel": [1200, 100, 1500, 300],
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
                "total_visits": 80,
                "unique_visitors": 75,
                "avg_dwell_seconds": 90.0,
                "median_dwell_seconds": 80.0,
                "p95_dwell_seconds": 180.0,
                "peak_hour": 13,
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
                "avg_occupancy": 3.0,
                "max_occupancy": 12,
                "return_rate": 0.02,
                "density_people_per_m2_hr": 11.1,
            },
        },
        "flow": {"transitions": [], "top_paths": []},
        "temporal": {"time_bin_seconds": 300, "occupancy_matrix": {}},
    }
    p = tmp_path / "report.json"
    p.write_text(json.dumps(report))
    return p


@pytest.fixture()
def client(mock_report: Path) -> TestClient:
    """TestClient with no API key."""
    app = create_app(report_path=mock_report, openrouter_api_key="")
    return TestClient(app)


# ── health ─────────────────────────────────────────────────────

class TestHealth:
    def test_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["video_id"] == "test_vid"
        assert data["n_zones"] == 3


# ── report ─────────────────────────────────────────────────────

class TestReport:
    def test_returns_zones(self, client: TestClient):
        resp = client.get("/api/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "zones" in data
        assert "zone_001" in data["zones"]
        assert "zone_002" in data["zones"]
        assert "zone_003" in data["zones"]


# ── chat ──────────────────────────────────────────────────────

def _parse_sse_events(resp) -> dict:
    """Collect all typed SSE events into a unified response dict."""
    result = {"text": "", "visualizations": [], "session_id": "", "actions": []}
    for line in resp.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        data = json.loads(payload)
        if "session_id" in data and not data.get("type"):
            result["session_id"] = data["session_id"]
        if data.get("type") == "text":
            result["text"] += data.get("content", "")
        if data.get("type") == "visualization":
            result["visualizations"].append(data["visualization"])
        if data.get("type") == "action":
            result["actions"].append(data["action"])
    return result


class TestChatNoApiKey:
    """When no API key is configured, chat returns an error message."""

    def test_returns_api_key_error(self, client: TestClient):
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200
        data = _parse_sse_events(resp)
        assert "API key" in data["text"]
        assert data["visualizations"] == []
        assert data["actions"] == []

    def test_creates_session_id(self, client: TestClient):
        resp = client.post("/api/chat", json={"message": "hello"})
        data = _parse_sse_events(resp)
        assert len(data["session_id"]) > 0

    def test_continues_session(self, client: TestClient):
        resp1 = client.post("/api/chat", json={"message": "hello"})
        data1 = _parse_sse_events(resp1)
        sid = data1["session_id"]

        resp2 = client.post(
            "/api/chat", json={"message": "show zones", "session_id": sid}
        )
        data2 = _parse_sse_events(resp2)
        assert data2["session_id"] == sid


# ── VLM JSON parser ──────────────────────────────────────────

class TestParseVlmJson:
    def test_plain_json(self):
        result = _parse_vlm_json('{"text": "hello", "visualizations": []}')
        assert result["text"] == "hello"
        assert result["actions"] == []

    def test_markdown_fenced_json(self):
        raw = '```json\n{"text": "hi", "visualizations": []}\n```'
        result = _parse_vlm_json(raw)
        assert result["text"] == "hi"

    def test_qwen_think_tags_stripped(self):
        raw = (
            '<think>Let me think about this...</think>'
            '{"action": "final_answer", "text": "done", "visualizations": []}'
        )
        result = _parse_vlm_json(raw)
        assert result.get("action") == "final_answer"
        assert result["text"] == "done"

    def test_tool_call_format(self):
        raw = '{"action": "query_zones", "action_input": {"limit": 3}}'
        result = _parse_vlm_json(raw)
        assert result["action"] == "query_zones"
        assert result["action_input"]["limit"] == 3

    def test_actions_key_defaulted(self):
        raw = '{"text": "hello", "visualizations": []}'
        result = _parse_vlm_json(raw)
        assert "actions" in result
        assert result["actions"] == []

    def test_brace_extraction_fallback(self):
        raw = 'Some preamble text {"text": "extracted", "visualizations": []} trailing'
        result = _parse_vlm_json(raw)
        assert result["text"] == "extracted"

    def test_unparseable_returns_raw_text(self):
        raw = "This is not JSON at all"
        result = _parse_vlm_json(raw)
        assert result["text"] == raw
        assert result["visualizations"] == []
        assert result["actions"] == []

    def test_think_tags_with_fenced_json(self):
        raw = (
            '<think>Planning my response...</think>\n'
            '```json\n'
            '{"action": "final_answer", "text": "result", "visualizations": [{"type": "kpi_cards"}]}\n'
            '```'
        )
        result = _parse_vlm_json(raw)
        assert result["action"] == "final_answer"
        assert result["text"] == "result"
        assert len(result["visualizations"]) == 1
