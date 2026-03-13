"""Tests for Module A: TrackDatabase."""

import numpy as np
import pytest

from tracker.database import TrackDatabase


class TestTrackDatabase:
    """Database layer tests."""

    def test_schema_initialized(self, tmp_db):
        tables = tmp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "videos" in table_names
        assert "detections" in table_names
        assert "tracks" in table_names
        assert "keyframes" in table_names
        assert "zones" in table_names

    def test_insert_video(self, tmp_db):
        tmp_db.insert_video("v1", "test.mp4", 30.0, 9000, 1920, 1080)
        video = tmp_db.get_video("v1")
        assert video is not None
        assert video["fps"] == 30.0
        assert video["width"] == 1920

    def test_insert_detections_batch(self, tmp_db):
        tmp_db.insert_video("v1", "test.mp4", 30.0, 1000, 1920, 1080)
        detections = [
            {
                "video_id": "v1",
                "frame_idx": i,
                "timestamp": i / 30.0,
                "track_id": 1,
                "x_center": 500.0,
                "y_center": 400.0,
                "bbox_x1": 480.0,
                "bbox_y1": 350.0,
                "bbox_x2": 520.0,
                "bbox_y2": 450.0,
                "bbox_w": 40.0,
                "bbox_h": 100.0,
                "confidence": 0.9,
                "object_class": "person",
            }
            for i in range(100)
        ]
        tmp_db.insert_detections_batch(detections)
        count = tmp_db.get_detection_count("v1")
        assert count == 100

    def test_keyframe_storage(self, tmp_db):
        tmp_db.insert_video("v1", "test.mp4", 30.0, 1000, 1920, 1080)
        frame = np.full((1080, 1920, 3), 128, dtype=np.uint8)
        tmp_db.insert_keyframe("v1", 0, frame)

        indices = tmp_db.get_keyframe_indices("v1")
        assert 0 in indices

        result = tmp_db.get_reference_frame("v1")
        assert result is not None
        frame_idx, retrieved = result
        assert frame_idx == 0
        assert retrieved.shape == (1080, 1920, 3)

    def test_compute_track_summaries(self, tmp_db):
        tmp_db.insert_video("v1", "test.mp4", 30.0, 1000, 1920, 1080)
        detections = []
        for frame in range(50):
            detections.append({
                "video_id": "v1",
                "frame_idx": frame,
                "timestamp": frame / 30.0,
                "track_id": 1,
                "x_center": 500.0 + frame,
                "y_center": 400.0,
                "bbox_x1": 480.0 + frame,
                "bbox_y1": 350.0,
                "bbox_x2": 520.0 + frame,
                "bbox_y2": 450.0,
                "bbox_w": 40.0,
                "bbox_h": 100.0,
                "confidence": 0.85,
                "object_class": "person",
            })
        tmp_db.insert_detections_batch(detections)
        tmp_db.compute_track_summaries("v1")

        summaries = tmp_db.get_track_summaries("v1")
        assert len(summaries) == 1
        assert summaries[0]["track_id"] == 1
        assert summaries[0]["num_detections"] == 50

    def test_save_and_retrieve_zones(self, tmp_db):
        tmp_db.insert_video("v1", "test.mp4", 30.0, 1000, 1920, 1080)
        zones = {
            "zone_001": {
                "zone_id": "zone_001",
                "business_name": "Test Zone",
                "zone_type": "fast_food",
                "polygon_bev": [[0, 0], [10, 0], [10, 10], [0, 10]],
                "area_m2": 100,
            }
        }
        tmp_db.save_zones("v1", zones)

        # Verify stored
        rows = tmp_db.conn.execute(
            "SELECT * FROM zones WHERE video_id = ?", ("v1",)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["zone_id"] == "zone_001"
