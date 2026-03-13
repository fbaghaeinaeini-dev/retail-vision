-- RetailVision Database Schema
-- Module A populates: videos, detections, tracks, keyframes
-- Module B populates: zones, zone_analytics, zone_transitions, pipeline_runs

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    fps REAL NOT NULL,
    total_frames INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    duration_seconds REAL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    track_id INTEGER NOT NULL,
    x_center REAL NOT NULL,
    y_center REAL NOT NULL,
    bbox_x1 REAL,
    bbox_y1 REAL,
    bbox_x2 REAL,
    bbox_y2 REAL,
    bbox_w REAL,
    bbox_h REAL,
    confidence REAL,
    object_class TEXT DEFAULT 'person',
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE INDEX IF NOT EXISTS idx_det_vt ON detections(video_id, track_id);
CREATE INDEX IF NOT EXISTS idx_det_vf ON detections(video_id, frame_idx);

CREATE TABLE IF NOT EXISTS tracks (
    video_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    first_frame INTEGER,
    last_frame INTEGER,
    first_timestamp REAL,
    last_timestamp REAL,
    duration_seconds REAL,
    duration_frames INTEGER,
    num_detections INTEGER,
    avg_confidence REAL,
    path_length_pixels REAL,
    avg_speed_px_per_sec REAL,
    quality_score REAL DEFAULT 0.5,
    gender TEXT,
    age_group TEXT,
    PRIMARY KEY (video_id, track_id),
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE IF NOT EXISTS keyframes (
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    frame_data BLOB NOT NULL,
    PRIMARY KEY (video_id, frame_idx),
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

-- Populated by Module B
CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    business_name TEXT,
    zone_type TEXT,
    description TEXT,
    vlm_confidence REAL,
    polygon_bev_json TEXT,
    polygon_pixel_json TEXT,
    centroid_bev_x REAL,
    centroid_bev_y REAL,
    area_m2 REAL,
    objects_json TEXT,
    signage_json TEXT,
    depth_info_json TEXT,
    strategy_agreement INTEGER,
    contributing_strategies TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE IF NOT EXISTS zone_analytics (
    zone_id TEXT PRIMARY KEY,
    total_visits INTEGER,
    unique_visitors INTEGER,
    avg_dwell_seconds REAL,
    median_dwell_seconds REAL,
    p95_dwell_seconds REAL,
    peak_hour INTEGER,
    hourly_visits_json TEXT,
    gender_distribution_json TEXT,
    avg_occupancy REAL,
    max_occupancy INTEGER,
    return_rate REAL,
    density_people_per_m2_hr REAL,
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS zone_transitions (
    from_zone TEXT,
    to_zone TEXT,
    count INTEGER,
    avg_travel_seconds REAL,
    probability REAL,
    PRIMARY KEY (from_zone, to_zone),
    FOREIGN KEY (from_zone) REFERENCES zones(zone_id),
    FOREIGN KEY (to_zone) REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,
    config_json TEXT,
    validation_metrics_json TEXT,
    n_zones_discovered INTEGER,
    calibration_method TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);
