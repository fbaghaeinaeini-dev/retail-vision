"""Phase 3a Tool: Quick zone analytics for VLM classification context.

Computes basic behavioral metrics (visits, dwell time, peak hour) BEFORE
zone classification, so the VLM has real data instead of 'N/A'.
Runs after fusion (Phase 2) and crop (Phase 3), before classifier.
"""

from __future__ import annotations

import numpy as np
from loguru import logger
from shapely.geometry import Point, Polygon

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("compute_quick_zone_analytics")
def compute_quick_zone_analytics(state, config) -> ToolResult:
    """Compute basic per-zone behavioral metrics for classifier context.

    Lighter than full compute_zone_analytics — only computes what the
    VLM classifier needs: visits, avg dwell, peak hour, flow pattern.
    """
    zones = state.fused_zones_dict or {}
    df = state.raw_tracks

    if not zones or df is None or df.empty or "bev_x_meters" not in df.columns:
        state.quick_zone_analytics = {}
        return ToolResult(success=True, message="No data for quick analytics", data={})

    # Build zone polygons
    zone_polys = {}
    for zid, z in zones.items():
        pts = z.get("polygon_bev", [])
        if len(pts) >= 3:
            try:
                zone_polys[zid] = Polygon(pts)
            except Exception:
                continue

    if not zone_polys:
        state.quick_zone_analytics = {}
        return ToolResult(success=True, message="No valid zone polygons", data={})

    # Sample tracks for speed (max 50k points)
    sample = df if len(df) <= 50_000 else df.sample(50_000, random_state=42)

    # Assign detections to zones
    zone_visits: dict[str, dict] = {zid: {"tracks": set(), "timestamps": []}
                                     for zid in zone_polys}

    for _, row in sample.iterrows():
        pt = Point(row["bev_x_meters"], row["bev_y_meters"])
        for zid, poly in zone_polys.items():
            if poly.contains(pt):
                zone_visits[zid]["tracks"].add(row["track_id"])
                zone_visits[zid]["timestamps"].append(row["timestamp"])
                break

    # Compute per-zone metrics
    duration_hrs = max(state.video_duration_seconds / 3600, 0.01)
    quick_analytics = {}

    for zid in zones:
        visits = zone_visits.get(zid, {"tracks": set(), "timestamps": []})
        n_visitors = len(visits["tracks"])
        timestamps = sorted(visits["timestamps"])

        # Estimate avg dwell from consecutive timestamps per track
        avg_dwell = 0.0
        if timestamps and len(timestamps) > 1:
            gaps = np.diff(timestamps)
            dwell_gaps = gaps[gaps < 30]
            avg_dwell = float(np.mean(dwell_gaps)) if len(dwell_gaps) > 0 else 0.0

        # Peak hour
        peak_hour = 0
        if timestamps:
            hours = [int(t // 3600) % 24 for t in timestamps]
            if hours:
                peak_hour = max(set(hours), key=hours.count)

        visits_per_hour = n_visitors / duration_hrs

        quick_analytics[zid] = {
            "total_visits": n_visitors,
            "avg_dwell_seconds": round(avg_dwell, 1),
            "visits_per_hour": round(visits_per_hour, 1),
            "peak_hour": peak_hour,
        }

    state.quick_zone_analytics = quick_analytics

    return ToolResult(
        success=True,
        data={"n_zones_analyzed": len(quick_analytics)},
        message=f"Quick analytics for {len(quick_analytics)} zones",
    )
