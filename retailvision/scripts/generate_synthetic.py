"""Generate realistic synthetic CCTV tracking data with known ground truth zones.

Creates a SQLite database with simulated person tracks through a food court
scene. Includes perspective effects (bbox_h decreases with y position).

Ground truth zones:
- Subway (fast_food, top-left, high dwell)
- Pizza Hut (fast_food, top-center, medium dwell)
- Starbucks (cafe, top-right, high dwell)
- Seating Area (seating, center, highest dwell)
- Main Corridor (corridor, horizontal band, low dwell)
- Entrance (entrance, left edge, zero dwell)

Usage:
    python -m scripts.generate_synthetic --db data/synthetic.db --n-tracks 500
"""

from pathlib import Path

import click
import cv2
import numpy as np
from loguru import logger

from tracker.database import TrackDatabase

# Ground truth zones in pixel coordinates (1920x1080)
GROUND_TRUTH_ZONES = {
    "subway": {
        "center": (300, 180),
        "size": (200, 150),
        "type": "fast_food",
        "dwell_mean": 180,
        "dwell_std": 60,
        "visit_weight": 0.20,
    },
    "pizza_hut": {
        "center": (960, 160),
        "size": (220, 140),
        "type": "fast_food",
        "dwell_mean": 120,
        "dwell_std": 45,
        "visit_weight": 0.18,
    },
    "starbucks": {
        "center": (1600, 200),
        "size": (200, 160),
        "type": "cafe",
        "dwell_mean": 240,
        "dwell_std": 90,
        "visit_weight": 0.22,
    },
    "seating": {
        "center": (960, 540),
        "size": (500, 250),
        "type": "seating_area",
        "dwell_mean": 300,
        "dwell_std": 120,
        "visit_weight": 0.25,
    },
    "corridor": {
        "center": (960, 800),
        "size": (1600, 120),
        "type": "corridor",
        "dwell_mean": 5,
        "dwell_std": 3,
        "visit_weight": 0.0,  # Transit only
    },
    "entrance": {
        "center": (100, 900),
        "size": (150, 180),
        "type": "entrance",
        "dwell_mean": 2,
        "dwell_std": 1,
        "visit_weight": 0.0,
    },
}

# Entry/exit points (edges of frame)
ENTRY_POINTS = [
    (100, 900),   # Main entrance (left-bottom)
    (1850, 900),  # Side entrance (right-bottom)
    (960, 1050),  # Bottom corridor exit
]


def _perspective_bbox_h(y: float, img_h: int = 1080) -> float:
    """Simulate perspective: bbox_h decreases with y (further from camera at top)."""
    # Vanishing point above frame
    y_vp = -500
    K = 1.7 * 800  # focal * person_height
    h = K / (y - y_vp + 1e-6)
    return max(20, min(h, 400))


def _generate_dwell_segment(
    center: tuple[float, float],
    duration_frames: int,
    fps: float,
) -> list[tuple[float, float]]:
    """Generate a 'loitering' segment around a center point."""
    points = []
    x, y = center
    for _ in range(duration_frames):
        # Small random walk within a confined area
        x += np.random.normal(0, 2)
        y += np.random.normal(0, 2)
        # Keep within zone bounds
        x = np.clip(x, center[0] - 30, center[0] + 30)
        y = np.clip(y, center[1] - 20, center[1] + 20)
        points.append((x, y))
    return points


def _generate_transit_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    speed_px_per_frame: float = 4.0,
) -> list[tuple[float, float]]:
    """Generate a smooth walk from start to end."""
    sx, sy = start
    ex, ey = end
    dist = np.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
    n_frames = max(int(dist / speed_px_per_frame), 2)

    points = []
    for i in range(n_frames):
        t = i / (n_frames - 1)
        x = sx + t * (ex - sx) + np.random.normal(0, 1.5)
        y = sy + t * (ey - sy) + np.random.normal(0, 1.5)
        points.append((x, y))
    return points


def generate_track(
    track_id: int,
    fps: float,
    rng: np.random.Generator,
) -> list[dict]:
    """Generate a single person track through the food court."""
    # Choose entry point
    entry = ENTRY_POINTS[rng.choice(len(ENTRY_POINTS))]

    # Choose 1-4 zones to visit
    zone_names = [z for z, d in GROUND_TRUTH_ZONES.items() if d["visit_weight"] > 0]
    weights = np.array([GROUND_TRUTH_ZONES[z]["visit_weight"] for z in zone_names])
    weights /= weights.sum()
    n_visits = rng.choice([1, 2, 3, 4], p=[0.15, 0.35, 0.35, 0.15])
    visited = rng.choice(zone_names, size=min(n_visits, len(zone_names)), replace=False, p=weights)

    # Build path: entry → zone1 → zone2 → ... → exit
    all_points: list[tuple[float, float]] = []

    current_pos = entry
    for zone_name in visited:
        zone = GROUND_TRUTH_ZONES[zone_name]

        # Add jitter to zone center for variety
        target = (
            zone["center"][0] + rng.normal(0, zone["size"][0] * 0.15),
            zone["center"][1] + rng.normal(0, zone["size"][1] * 0.15),
        )

        # Transit to zone (through corridor if needed)
        if abs(current_pos[1] - target[1]) > 200:
            # Go through corridor first
            corridor_y = GROUND_TRUTH_ZONES["corridor"]["center"][1]
            mid = (current_pos[0] + (target[0] - current_pos[0]) * 0.5, corridor_y)
            all_points.extend(_generate_transit_segment(current_pos, mid))
            current_pos = mid

        all_points.extend(_generate_transit_segment(current_pos, target))
        current_pos = target

        # Dwell in zone
        dwell_sec = max(3, rng.normal(zone["dwell_mean"], zone["dwell_std"]))
        dwell_frames = int(dwell_sec * fps)
        all_points.extend(_generate_dwell_segment(target, dwell_frames, fps))
        current_pos = all_points[-1]

    # Exit
    exit_point = ENTRY_POINTS[rng.choice(len(ENTRY_POINTS))]
    all_points.extend(_generate_transit_segment(current_pos, exit_point))

    # Convert to detection records
    detections = []
    for i, (x, y) in enumerate(all_points):
        x = np.clip(x, 10, 1910)
        y = np.clip(y, 10, 1070)

        bbox_h = _perspective_bbox_h(y)
        bbox_w = bbox_h * 0.4  # Person aspect ratio
        conf = 0.5 + rng.random() * 0.45  # 0.5-0.95

        detections.append(
            {
                "video_id": "synthetic_v1",
                "frame_idx": i,
                "timestamp": i / fps,
                "track_id": track_id,
                "x_center": float(x),
                "y_center": float(y),
                "bbox_x1": float(x - bbox_w / 2),
                "bbox_y1": float(y - bbox_h / 2),
                "bbox_x2": float(x + bbox_w / 2),
                "bbox_y2": float(y + bbox_h / 2),
                "bbox_w": float(bbox_w),
                "bbox_h": float(bbox_h),
                "confidence": float(conf),
                "object_class": "person",
            }
        )

    return detections


def _create_synthetic_keyframe(W: int, H: int) -> np.ndarray:
    """Create a simple food court reference frame for testing."""
    frame = np.full((H, W, 3), (40, 40, 50), dtype=np.uint8)

    for name, zone in GROUND_TRUTH_ZONES.items():
        cx, cy = zone["center"]
        sw, sh = zone["size"]
        x1, y1 = int(cx - sw / 2), int(cy - sh / 2)
        x2, y2 = int(cx + sw / 2), int(cy + sh / 2)

        # Zone background
        color = {
            "fast_food": (50, 80, 180),
            "cafe": (60, 120, 160),
            "seating_area": (100, 100, 60),
            "corridor": (80, 80, 80),
            "entrance": (60, 140, 60),
        }.get(zone["type"], (100, 100, 100))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 200, 200), 1)

        # Label
        cv2.putText(
            frame, name.upper(), (x1 + 5, y1 + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1,
        )

    return frame


def generate_synthetic_dataset(
    db_path: str = "data/synthetic.db",
    n_tracks: int = 500,
    duration_min: float = 60,
    fps: float = 30.0,
    W: int = 1920,
    H: int = 1080,
    seed: int = 42,
):
    """Generate complete synthetic dataset with tracks and keyframes."""
    rng = np.random.default_rng(seed)
    db = TrackDatabase(db_path)

    video_id = "synthetic_v1"
    total_frames = int(duration_min * 60 * fps)
    db.insert_video(video_id, "synthetic", fps, total_frames, W, H)

    # Generate keyframe
    keyframe = _create_synthetic_keyframe(W, H)
    for fi in range(0, total_frames, 150):
        db.insert_keyframe(video_id, fi, keyframe)

    # Generate tracks with staggered start times
    logger.info(f"Generating {n_tracks} synthetic tracks...")
    all_detections: list[dict] = []

    for tid in range(1, n_tracks + 1):
        track_dets = generate_track(tid, fps, rng)

        # Offset frame indices to simulate staggered arrivals
        start_frame = rng.integers(0, max(1, total_frames - len(track_dets)))
        for d in track_dets:
            d["frame_idx"] = start_frame + d["frame_idx"]
            d["timestamp"] = d["frame_idx"] / fps

        all_detections.extend(track_dets)

    # Sort by frame_idx for realistic ordering
    all_detections.sort(key=lambda d: (d["frame_idx"], d["track_id"]))

    # Batch insert
    batch_size = 5000
    for i in range(0, len(all_detections), batch_size):
        db.insert_detections_batch(all_detections[i : i + batch_size])

    # Compute summaries
    db.compute_track_summaries(video_id)

    # Score quality
    tracks = db.get_track_summaries(video_id)
    for t in tracks:
        # Synthetic tracks are high quality by design
        quality = 0.6 + rng.random() * 0.35
        db.update_track_quality(video_id, t["track_id"], float(quality))

    det_count = db.get_detection_count(video_id)
    logger.success(
        f"Generated: {n_tracks} tracks, {det_count} detections, "
        f"{len(db.get_keyframe_indices(video_id))} keyframes"
    )
    db.close()

    return {
        "db_path": db_path,
        "video_id": video_id,
        "n_tracks": n_tracks,
        "n_detections": det_count,
        "ground_truth_zones": list(GROUND_TRUTH_ZONES.keys()),
    }


@click.command()
@click.option("--db", default="data/synthetic.db", help="Output database path")
@click.option("--n-tracks", default=500, type=int, help="Number of person tracks")
@click.option("--duration", default=60, type=float, help="Video duration in minutes")
@click.option("--seed", default=42, type=int, help="Random seed")
def main(db, n_tracks, duration, seed):
    """Generate synthetic CCTV tracking data."""
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    result = generate_synthetic_dataset(db, n_tracks, duration, seed=seed)
    logger.info(f"Result: {result}")


if __name__ == "__main__":
    main()
