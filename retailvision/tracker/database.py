"""SQLite database wrapper for RetailVision tracking data.

Handles all DB operations for Module A (tracker) and Module B (agent pipeline).
Uses WAL mode for concurrent read/write performance.
"""

import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class TrackDatabase:
    """Thread-safe SQLite wrapper with batch insert support."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self):
        schema_sql = SCHEMA_PATH.read_text()
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── Video metadata ──

    def insert_video(
        self,
        video_id: str,
        file_path: str,
        fps: float,
        total_frames: int,
        width: int,
        height: int,
    ):
        duration = total_frames / fps if fps > 0 else 0
        self.conn.execute(
            """INSERT OR REPLACE INTO videos
               (video_id, file_path, fps, total_frames, width, height, duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (video_id, file_path, fps, total_frames, width, height, duration),
        )
        self.conn.commit()
        logger.info(f"Video '{video_id}': {total_frames} frames @ {fps:.1f}fps, {width}x{height}")

    def get_video(self, video_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Detections (batch insert for performance) ──

    def insert_detections_batch(self, detections: list[dict]):
        self.conn.executemany(
            """INSERT INTO detections
               (video_id, frame_idx, timestamp, track_id,
                x_center, y_center, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                bbox_w, bbox_h, confidence, object_class)
               VALUES (:video_id, :frame_idx, :timestamp, :track_id,
                       :x_center, :y_center, :bbox_x1, :bbox_y1, :bbox_x2, :bbox_y2,
                       :bbox_w, :bbox_h, :confidence, :object_class)""",
            detections,
        )
        self.conn.commit()

    def get_detections(self, video_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM detections WHERE video_id = ? ORDER BY frame_idx, track_id",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_detection_count(self, video_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM detections WHERE video_id = ?", (video_id,)
        ).fetchone()
        return row["cnt"]

    # ── Keyframes ──

    def insert_keyframe(self, video_id: str, frame_idx: int, frame: np.ndarray):
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        self.conn.execute(
            "INSERT OR REPLACE INTO keyframes (video_id, frame_idx, frame_data) VALUES (?, ?, ?)",
            (video_id, frame_idx, buf.tobytes()),
        )
        self.conn.commit()

    def get_keyframe(self, video_id: str, frame_idx: int) -> np.ndarray | None:
        row = self.conn.execute(
            "SELECT frame_data FROM keyframes WHERE video_id = ? AND frame_idx = ?",
            (video_id, frame_idx),
        ).fetchone()
        if row is None:
            return None
        buf = np.frombuffer(row["frame_data"], dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def get_keyframe_indices(self, video_id: str) -> list[int]:
        rows = self.conn.execute(
            "SELECT frame_idx FROM keyframes WHERE video_id = ? ORDER BY frame_idx",
            (video_id,),
        ).fetchall()
        return [r["frame_idx"] for r in rows]

    def get_reference_frame(self, video_id: str) -> tuple[int, np.ndarray] | None:
        """Get the middle keyframe as the reference frame."""
        indices = self.get_keyframe_indices(video_id)
        if not indices:
            return None
        mid_idx = indices[len(indices) // 2]
        frame = self.get_keyframe(video_id, mid_idx)
        return (mid_idx, frame) if frame is not None else None

    # ── Track summaries ──

    def compute_track_summaries(self, video_id: str):
        """Compute per-track summary statistics from detections."""
        self.conn.execute(
            """INSERT OR REPLACE INTO tracks
               (video_id, track_id, first_frame, last_frame,
                first_timestamp, last_timestamp, duration_seconds, duration_frames,
                num_detections, avg_confidence, path_length_pixels, avg_speed_px_per_sec)
               SELECT
                 video_id, track_id,
                 MIN(frame_idx), MAX(frame_idx),
                 MIN(timestamp), MAX(timestamp),
                 MAX(timestamp) - MIN(timestamp),
                 MAX(frame_idx) - MIN(frame_idx) + 1,
                 COUNT(*),
                 AVG(confidence),
                 0.0, 0.0
               FROM detections
               WHERE video_id = ?
               GROUP BY video_id, track_id""",
            (video_id,),
        )
        self.conn.commit()

        # Compute path lengths
        tracks = self.get_track_summaries(video_id)
        for t in tracks:
            tid = t["track_id"]
            rows = self.conn.execute(
                """SELECT x_center, y_center FROM detections
                   WHERE video_id = ? AND track_id = ?
                   ORDER BY frame_idx""",
                (video_id, tid),
            ).fetchall()
            if len(rows) < 2:
                continue
            pts = np.array([(r["x_center"], r["y_center"]) for r in rows])
            diffs = np.diff(pts, axis=0)
            dists = np.sqrt((diffs**2).sum(axis=1))
            path_len = float(dists.sum())
            duration = max(t["duration_seconds"], 1e-6)
            avg_speed = path_len / duration

            self.conn.execute(
                """UPDATE tracks SET path_length_pixels = ?, avg_speed_px_per_sec = ?
                   WHERE video_id = ? AND track_id = ?""",
                (path_len, avg_speed, video_id, tid),
            )
        self.conn.commit()
        logger.info(f"Computed summaries for {len(tracks)} tracks")

    def get_track_summaries(self, video_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM tracks WHERE video_id = ? ORDER BY track_id", (video_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_track_quality(self, video_id: str, track_id: int, quality: float):
        self.conn.execute(
            "UPDATE tracks SET quality_score = ? WHERE video_id = ? AND track_id = ?",
            (quality, video_id, track_id),
        )
        self.conn.commit()

    def get_track_displacements(self, video_id: str, track_id: int) -> list[float]:
        rows = self.conn.execute(
            """SELECT x_center, y_center FROM detections
               WHERE video_id = ? AND track_id = ?
               ORDER BY frame_idx""",
            (video_id, track_id),
        ).fetchall()
        if len(rows) < 2:
            return []
        pts = np.array([(r["x_center"], r["y_center"]) for r in rows])
        diffs = np.diff(pts, axis=0)
        return np.sqrt((diffs**2).sum(axis=1)).tolist()

    # ── Module B: Zones ──

    def save_zones(self, video_id: str, zone_registry: dict):
        for zid, zone in zone_registry.items():
            self.conn.execute(
                """INSERT OR REPLACE INTO zones
                   (zone_id, video_id, business_name, zone_type, description,
                    vlm_confidence, polygon_bev_json, polygon_pixel_json,
                    centroid_bev_x, centroid_bev_y, area_m2,
                    objects_json, signage_json, depth_info_json,
                    strategy_agreement, contributing_strategies)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    zid,
                    video_id,
                    zone.get("business_name"),
                    zone.get("zone_type"),
                    zone.get("description"),
                    zone.get("vlm_confidence"),
                    json.dumps(zone.get("polygon_bev", [])),
                    json.dumps(zone.get("polygon_pixel", [])),
                    zone.get("centroid_bev", [0, 0])[0],
                    zone.get("centroid_bev", [0, 0])[1],
                    zone.get("area_m2", 0),
                    json.dumps(zone.get("objects", [])),
                    json.dumps(zone.get("signage", {})),
                    json.dumps(zone.get("depth_info", {})),
                    zone.get("strategy_agreement", 0),
                    json.dumps(zone.get("contributing_strategies", [])),
                ),
            )
        self.conn.commit()
        logger.info(f"Saved {len(zone_registry)} zones for video '{video_id}'")

    def save_zone_analytics(self, analytics: dict):
        for zid, data in analytics.items():
            self.conn.execute(
                """INSERT OR REPLACE INTO zone_analytics
                   (zone_id, total_visits, unique_visitors,
                    avg_dwell_seconds, median_dwell_seconds, p95_dwell_seconds,
                    peak_hour, hourly_visits_json, gender_distribution_json,
                    avg_occupancy, max_occupancy, return_rate, density_people_per_m2_hr)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    zid,
                    data.get("total_visits", 0),
                    data.get("unique_visitors", 0),
                    data.get("avg_dwell_seconds", 0),
                    data.get("median_dwell_seconds", 0),
                    data.get("p95_dwell_seconds", 0),
                    data.get("peak_hour", 0),
                    json.dumps(data.get("hourly_visits", {})),
                    json.dumps(data.get("gender_distribution", {})),
                    data.get("avg_occupancy", 0),
                    data.get("max_occupancy", 0),
                    data.get("return_rate", 0),
                    data.get("density_people_per_m2_hr", 0),
                ),
            )
        self.conn.commit()

    def save_zone_transitions(self, transitions: list[dict]):
        self.conn.executemany(
            """INSERT OR REPLACE INTO zone_transitions
               (from_zone, to_zone, count, avg_travel_seconds, probability)
               VALUES (:from_zone, :to_zone, :count, :avg_travel_seconds, :probability)""",
            transitions,
        )
        self.conn.commit()

    def save_pipeline_run(self, run_data: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO pipeline_runs
               (run_id, video_id, started_at, completed_at, status,
                config_json, validation_metrics_json, n_zones_discovered, calibration_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_data["run_id"],
                run_data["video_id"],
                run_data.get("started_at"),
                run_data.get("completed_at"),
                run_data.get("status"),
                json.dumps(run_data.get("config", {})),
                json.dumps(run_data.get("validation_metrics", {})),
                run_data.get("n_zones_discovered", 0),
                run_data.get("calibration_method"),
            ),
        )
        self.conn.commit()
