"""Tests for chat prompt builder utilities."""

from api.chat_prompt import VIZ_TYPES, build_system_prompt, summarize_report


class TestSummarizeReport:
    """Tests for summarize_report."""

    def test_produces_string_with_key_data(self):
        report = {
            "meta": {
                "video_id": "abc123",
                "scene_type": "indoor_food_court",
                "duration_seconds": 1800.0,
            },
            "zones": {
                "zone_001": {
                    "zone_id": "zone_001",
                    "business_name": "Cafe Corner",
                    "zone_type": "cafe",
                }
            },
            "analytics": {
                "zone_001": {
                    "total_visits": 500,
                    "avg_dwell_seconds": 45.2,
                    "peak_hour": 14,
                }
            },
            "flow": {
                "top_paths": [
                    {"from": "zone_001", "to": "zone_002", "count": 42},
                ]
            },
        }
        summary = summarize_report(report)
        assert isinstance(summary, str)
        assert "abc123" in summary
        assert "Cafe Corner" in summary
        assert "500" in summary
        assert "45.2" in summary
        assert "zone_001" in summary

    def test_handles_empty_report(self):
        summary = summarize_report({})
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_handles_no_analytics(self):
        report = {
            "meta": {"video_id": "v1"},
            "zones": {"z1": {"zone_id": "z1", "business_name": "Z", "zone_type": "x"}},
        }
        summary = summarize_report(report)
        assert "v1" in summary
        assert "Z" in summary


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_contains_all_viz_types(self):
        prompt = build_system_prompt("some summary")
        for vt in VIZ_TYPES:
            assert vt in prompt, f"Missing viz type: {vt}"

    def test_includes_summary(self):
        summary = "VIDEO_SUMMARY_TOKEN_XYZ"
        prompt = build_system_prompt(summary)
        assert summary in prompt

    def test_instructs_json_response(self):
        prompt = build_system_prompt("s")
        assert "final_answer" in prompt
        assert "text" in prompt
        assert "visualizations" in prompt
