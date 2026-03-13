"""Phase 2 Tool t07: Dwell point detection with BEV confinement filter.

Identifies locations where people stop and linger (dwell), filtering out
straight slow walks using confinement radius and curvature checks.
All spatial computation in BEV meters.
"""

import numpy as np
from loguru import logger

from agent.models import DwellPoint, ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("compute_dwell_points")
def compute_dwell_points(state, config) -> ToolResult:
    """t07: Detect dwell events from BEV-calibrated tracks.

    For each track, segments slow periods and applies confinement + curvature
    filters to distinguish true dwelling from slow walking.
    """
    df = state.raw_tracks
    if df is None or "bev_x_meters" not in df.columns:
        return ToolResult(success=False, message="BEV-calibrated tracks required")

    speed_thresh = config.dwell_speed_threshold_m_s
    min_dwell = config.min_dwell_seconds
    max_confinement = config.confinement_radius_m
    min_curvature = config.min_curvature_rad

    dwell_points = []

    for track_id, group in df.groupby("track_id"):
        if len(group) < 5:
            continue

        speeds = group["speed_m_s"].values
        timestamps = group["timestamp"].values
        bev_x = group["bev_x_meters"].values
        bev_y = group["bev_y_meters"].values
        frames = group["frame_idx"].values

        # Find slow segments
        is_slow = speeds < speed_thresh
        segments = _find_segments(is_slow)

        for start_idx, end_idx in segments:
            seg_x = bev_x[start_idx:end_idx + 1]
            seg_y = bev_y[start_idx:end_idx + 1]
            seg_t = timestamps[start_idx:end_idx + 1]

            duration = seg_t[-1] - seg_t[0]
            if duration < min_dwell:
                continue

            # Confinement check
            centroid_x = np.mean(seg_x)
            centroid_y = np.mean(seg_y)
            distances = np.sqrt((seg_x - centroid_x) ** 2 + (seg_y - centroid_y) ** 2)
            confinement = float(np.max(distances))

            if confinement > max_confinement:
                continue  # Too spread out — walking, not dwelling

            # Curvature check: sum of heading changes
            if len(seg_x) > 2:
                dx = np.diff(seg_x)
                dy = np.diff(seg_y)
                headings = np.arctan2(dy, dx)
                heading_changes = np.abs(np.diff(headings))
                heading_changes = np.minimum(heading_changes, 2 * np.pi - heading_changes)
                curvature = float(np.sum(heading_changes))
            else:
                curvature = 0.0

            if curvature < min_curvature:
                continue  # Straight slow walk, not loitering

            dwell_points.append(
                DwellPoint(
                    track_id=int(track_id),
                    centroid_bev=[float(centroid_x), float(centroid_y)],
                    duration_seconds=float(duration),
                    confinement_radius_m=confinement,
                    start_frame=int(frames[start_idx]),
                    end_frame=int(frames[end_idx]),
                    curvature=curvature,
                )
            )

    state.dwell_points = dwell_points

    return ToolResult(
        success=True,
        data={
            "n_dwell_points": len(dwell_points),
            "avg_dwell_seconds": float(np.mean([d.duration_seconds for d in dwell_points]))
            if dwell_points else 0,
        },
        message=f"Found {len(dwell_points)} dwell events "
                f"(thresh: speed<{speed_thresh}m/s, dur>{min_dwell}s, conf<{max_confinement}m)",
    )


def _find_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    """Find contiguous True segments in a boolean array."""
    segments = []
    in_segment = False
    start = 0

    for i, val in enumerate(mask):
        if val and not in_segment:
            start = i
            in_segment = True
        elif not val and in_segment:
            segments.append((start, i - 1))
            in_segment = False

    if in_segment:
        segments.append((start, len(mask) - 1))

    return segments
