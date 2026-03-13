"""Integration tests: run multi-phase pipeline segments offline."""

import json
from pathlib import Path

import pytest


class TestPhase1To2Integration:
    """Test Phase 1 → Phase 2 flow (calibration → dwell → strategies → fusion)."""

    def test_calibrate_then_discover_zones(self, calibrated_state, config):
        """Run the full discovery pipeline on pre-calibrated state."""
        from agent.tools.phase2_dwell import compute_dwell_points
        from agent.tools.phase2_strategy_a import strategy_dwell_clustering
        from agent.tools.phase2_strategy_b import strategy_occupancy_grid
        from agent.tools.phase2_strategy_c import strategy_trajectory_graph
        from agent.tools.phase2_fusion import fuse_zone_candidates

        r1 = compute_dwell_points(calibrated_state, config)
        assert r1.success

        r2 = strategy_dwell_clustering(calibrated_state, config)
        assert r2.success

        r3 = strategy_occupancy_grid(calibrated_state, config)
        assert r3.success

        r4 = strategy_trajectory_graph(calibrated_state, config)
        assert r4.success

        r5 = fuse_zone_candidates(calibrated_state, config)
        assert r5.success


class TestPhase3MergeIntegration:
    """Test Phase 3: enrichment → merge."""

    def test_merge_without_vlm(self, discovered_state, config):
        """Merge should work with pre-stubbed classifications (no API calls)."""
        from agent.tools.phase3_merge import merge_zone_registry

        result = merge_zone_registry(discovered_state, config)
        assert result.success
        assert len(discovered_state.zone_registry) >= 3

        # All zones should have valid types
        for zid, zone in discovered_state.zone_registry.items():
            assert zone["zone_type"] in [
                "fast_food", "cafe", "seating_area", "corridor",
                "entrance", "exit", "shop", "kiosk", "restaurant",
                "service_counter", "waiting_area", "open_space", "unknown",
            ]


class TestPhase4To6Integration:
    """Test analytics → validation → export pipeline."""

    def test_analytics_through_export(self, discovered_state, config, tmp_path):
        """Run Phases 4-6 end-to-end."""
        config.output_dir = tmp_path / "output"

        from agent.tools.phase3_merge import merge_zone_registry
        from agent.tools.phase4_analytics import (
            compute_zone_analytics,
            compute_flow_analytics,
            compute_temporal_analytics,
            compute_spatial_analytics,
        )
        from agent.tools.phase5_validate import validate_zones, quality_gate
        from agent.tools.phase6_visualize import (
            plan_visualizations,
            render_all_visualizations,
            render_3d_scene,
            export_dashboard_bundle,
        )

        # Phase 3
        merge_zone_registry(discovered_state, config)

        # Phase 4
        compute_zone_analytics(discovered_state, config)
        compute_flow_analytics(discovered_state, config)
        compute_temporal_analytics(discovered_state, config)
        compute_spatial_analytics(discovered_state, config)

        # Phase 5
        r_val = validate_zones(discovered_state, config)
        assert r_val.success
        r_gate = quality_gate(discovered_state, config)
        assert r_gate.success

        # Phase 6
        plan_visualizations(discovered_state, config)
        assert len(discovered_state.visualization_plan) > 0

        render_all_visualizations(discovered_state, config)
        render_3d_scene(discovered_state, config)

        # Export (needs DB)
        from tracker.database import TrackDatabase
        db = TrackDatabase(config.db_path)
        db.insert_video("test_v1", "test.mp4", 30.0, 54000, 1920, 1080)
        db.close()

        r_export = export_dashboard_bundle(discovered_state, config)
        assert r_export.success

        # Verify output files
        report_path = Path(config.output_dir) / "report.json"
        assert report_path.exists()

        with open(report_path) as f:
            report = json.load(f)

        assert "meta" in report
        assert "zones" in report
        assert len(report["zones"]) >= 3
        assert report["meta"]["video_id"] == "test_v1"

        scene_path = Path(config.output_dir) / "3d_scene.json"
        assert scene_path.exists()


class TestSyntheticDataGenerator:
    """Test the synthetic data generator."""

    def test_generate_small_dataset(self, tmp_path):
        from scripts.generate_synthetic import generate_synthetic_dataset

        result = generate_synthetic_dataset(
            db_path=str(tmp_path / "synth.db"),
            n_tracks=10,
            duration_min=5,
            seed=42,
        )

        assert result["n_tracks"] == 10
        assert result["n_detections"] > 0
        assert "subway" in result["ground_truth_zones"]

        # Verify DB is valid
        from tracker.database import TrackDatabase
        db = TrackDatabase(tmp_path / "synth.db")
        video = db.get_video("synthetic_v1")
        assert video is not None
        db.close()
