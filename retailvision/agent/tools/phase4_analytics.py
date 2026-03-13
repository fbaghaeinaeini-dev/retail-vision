"""Phase 4 Analytics Tools: t20-t23.

Compute zone, flow, temporal, and spatial analytics.
All operate in BEV meters and produce structured data for the dashboard.
"""

import numpy as np
from collections import defaultdict
from loguru import logger
from shapely.geometry import Point, Polygon

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


def _assign_tracks_to_zones(df, zone_registry):
    """Assign each detection to a zone based on BEV coordinates."""
    if not zone_registry or "bev_x_meters" not in df.columns:
        return {}

    # Build zone polygons
    zone_polys = {}
    for zid, zone in zone_registry.items():
        poly_pts = zone.get("polygon_bev", [])
        if len(poly_pts) >= 3:
            try:
                zone_polys[zid] = Polygon(poly_pts)
            except Exception:
                continue

    # Assign points to zones (sampled for performance)
    assignments = {}  # frame_idx+track_id → zone_id
    sample = df if len(df) < 100000 else df.sample(100000, random_state=42)

    for _, row in sample.iterrows():
        pt = Point(row["bev_x_meters"], row["bev_y_meters"])
        for zid, poly in zone_polys.items():
            if poly.contains(pt):
                key = (int(row["track_id"]), int(row["frame_idx"]))
                assignments[key] = zid
                break

    return assignments


@ToolRegistry.register("compute_zone_analytics")
def compute_zone_analytics(state, config) -> ToolResult:
    """t20: Per-zone analytics — visits, dwell time, demographics, peak hours."""
    df = state.raw_tracks
    registry = state.zone_registry

    if not registry:
        return ToolResult(success=True, data={}, message="No zones to analyze")

    assignments = _assign_tracks_to_zones(df, registry)

    # Track → zones visited with timestamps
    track_zones = defaultdict(list)  # track_id → [(zone_id, timestamp)]
    for (tid, fidx), zid in assignments.items():
        ts = df.loc[(df["track_id"] == tid) & (df["frame_idx"] == fidx), "timestamp"]
        if not ts.empty:
            track_zones[tid].append((zid, float(ts.iloc[0])))

    # Sort by timestamp
    for tid in track_zones:
        track_zones[tid].sort(key=lambda x: x[1])

    analytics = {}
    duration_hrs = max(state.video_duration_seconds / 3600, 1e-6)

    for zid in registry:
        # Find visits to this zone
        zone_visits = []
        for tid, visits in track_zones.items():
            zone_segments = [(z, t) for z, t in visits if z == zid]
            if zone_segments:
                entry_time = zone_segments[0][1]
                exit_time = zone_segments[-1][1]
                dwell = exit_time - entry_time
                zone_visits.append({
                    "track_id": tid,
                    "entry_time": entry_time,
                    "dwell_seconds": max(dwell, 1.0),
                })

        if not zone_visits:
            analytics[zid] = _empty_analytics()
            continue

        dwells = [v["dwell_seconds"] for v in zone_visits]
        hours = [int(v["entry_time"] / 3600) % 24 for v in zone_visits]

        # Hourly distribution
        hourly = defaultdict(int)
        for h in hours:
            hourly[h] += 1

        peak_hour = max(hourly, key=hourly.get) if hourly else 0
        area_m2 = registry[zid].get("area_m2", 1)

        analytics[zid] = {
            "total_visits": len(zone_visits),
            "unique_visitors": len(set(v["track_id"] for v in zone_visits)),
            "avg_dwell_seconds": float(np.mean(dwells)),
            "median_dwell_seconds": float(np.median(dwells)),
            "p95_dwell_seconds": float(np.percentile(dwells, 95)),
            "peak_hour": peak_hour,
            "hourly_visits": dict(hourly),
            "avg_occupancy": len(zone_visits) / (duration_hrs * 60),
            "max_occupancy": max(hourly.values()) if hourly else 0,
            "return_rate": 0.0,  # Would need multi-day data
            "density_people_per_m2_hr": len(zone_visits) / (duration_hrs * area_m2),
        }

    state.zone_analytics = analytics
    return ToolResult(
        success=True,
        data={"n_zones_analyzed": len(analytics)},
        message=f"Computed analytics for {len(analytics)} zones",
    )


@ToolRegistry.register("compute_flow_analytics")
def compute_flow_analytics(state, config) -> ToolResult:
    """t21: Zone-to-zone transition flows for Sankey diagram."""
    df = state.raw_tracks
    registry = state.zone_registry

    if not registry:
        return ToolResult(success=True, data={}, message="No zones for flow analysis")

    assignments = _assign_tracks_to_zones(df, registry)

    # Build per-track zone sequence
    track_sequences = defaultdict(list)
    for (tid, fidx), zid in sorted(assignments.items(), key=lambda x: x[0][1]):
        track_sequences[tid].append(zid)

    # Deduplicate consecutive same-zone entries
    transitions = defaultdict(int)
    for tid, seq in track_sequences.items():
        deduped = [seq[0]]
        for z in seq[1:]:
            if z != deduped[-1]:
                deduped.append(z)
        for i in range(len(deduped) - 1):
            transitions[(deduped[i], deduped[i + 1])] += 1

    # Compute probabilities
    from_totals = defaultdict(int)
    for (fz, tz), count in transitions.items():
        from_totals[fz] += count

    flow_data = []
    for (fz, tz), count in transitions.items():
        flow_data.append({
            "from_zone": fz,
            "to_zone": tz,
            "count": count,
            "probability": count / max(from_totals[fz], 1),
            "avg_travel_seconds": 0,  # Would need per-transition timing
        })

    state.flow_analytics = {
        "transitions": flow_data,
        "top_paths": sorted(flow_data, key=lambda x: x["count"], reverse=True)[:10],
    }

    return ToolResult(
        success=True,
        data={"n_transitions": len(flow_data)},
        message=f"Computed {len(flow_data)} zone-to-zone transitions",
    )


@ToolRegistry.register("compute_temporal_analytics")
def compute_temporal_analytics(state, config) -> ToolResult:
    """t22: Temporal analytics — occupancy time series, rush detection."""
    df = state.raw_tracks
    registry = state.zone_registry

    if not registry or "timestamp" not in df.columns:
        state.temporal_analytics = {}
        return ToolResult(success=True, data={}, message="No data for temporal analysis")

    assignments = _assign_tracks_to_zones(df, registry)

    # Build zone × time_bin occupancy matrix
    time_bin_seconds = 300  # 5-minute bins
    max_time = df["timestamp"].max()
    n_bins = int(max_time / time_bin_seconds) + 1

    occupancy_matrix = {}
    for zid in registry:
        occupancy_matrix[zid] = [0] * min(n_bins, 1000)

    for (tid, fidx), zid in assignments.items():
        ts = df.loc[(df["track_id"] == tid) & (df["frame_idx"] == fidx), "timestamp"]
        if not ts.empty:
            time_bin = int(ts.iloc[0] / time_bin_seconds)
            if time_bin < len(occupancy_matrix.get(zid, [])):
                occupancy_matrix[zid][time_bin] += 1

    # Rush detection: bins with occupancy > 2x median
    rush_periods = {}
    for zid, occ in occupancy_matrix.items():
        if not occ:
            continue
        median_occ = max(np.median(occ), 1)
        rush_periods[zid] = [
            i for i, v in enumerate(occ) if v > 2 * median_occ
        ]

    state.temporal_analytics = {
        "occupancy_matrix": occupancy_matrix,
        "time_bin_seconds": time_bin_seconds,
        "rush_periods": rush_periods,
    }

    return ToolResult(
        success=True,
        data={"n_time_bins": n_bins, "n_rush_zones": sum(1 for v in rush_periods.values() if v)},
        message=f"Temporal analysis: {n_bins} time bins, "
                f"{sum(1 for v in rush_periods.values() if v)} zones with rush periods",
    )


@ToolRegistry.register("compute_spatial_analytics")
def compute_spatial_analytics(state, config) -> ToolResult:
    """t23: Spatial analytics — BEV density heatmap, depth-informed metrics."""
    df = state.raw_tracks

    if "bev_x_meters" not in df.columns:
        state.spatial_analytics = {}
        return ToolResult(success=True, data={}, message="No BEV data for spatial analysis")

    bev_x = df["bev_x_meters"].values
    bev_y = df["bev_y_meters"].values

    # BEV density heatmap
    x_min, x_max = bev_x.min(), bev_x.max()
    y_min, y_max = bev_y.min(), bev_y.max()
    cell = 0.5  # 0.5m cells

    grid_w = min(int((x_max - x_min) / cell) + 1, 1000)
    grid_h = min(int((y_max - y_min) / cell) + 1, 1000)

    heatmap = np.zeros((grid_h, grid_w), dtype=np.float32)
    gx = np.clip(((bev_x - x_min) / cell).astype(int), 0, grid_w - 1)
    gy = np.clip(((bev_y - y_min) / cell).astype(int), 0, grid_h - 1)
    np.add.at(heatmap, (gy, gx), 1)

    # Normalize
    duration_hrs = max(state.video_duration_seconds / 3600, 1e-6)
    heatmap_density = heatmap / (duration_hrs * cell ** 2)

    state.spatial_analytics = {
        "heatmap_density": heatmap_density.tolist(),
        "heatmap_bounds": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "cell_size_m": cell,
        "peak_density": float(heatmap_density.max()),
    }

    return ToolResult(
        success=True,
        data={"grid_size": f"{grid_w}x{grid_h}", "peak_density": float(heatmap_density.max())},
        message=f"Spatial heatmap: {grid_w}x{grid_h} grid, peak density {heatmap_density.max():.1f}/m²/hr",
    )


def _empty_analytics():
    return {
        "total_visits": 0, "unique_visitors": 0,
        "avg_dwell_seconds": 0, "median_dwell_seconds": 0, "p95_dwell_seconds": 0,
        "peak_hour": 0, "hourly_visits": {},
        "avg_occupancy": 0, "max_occupancy": 0,
        "return_rate": 0, "density_people_per_m2_hr": 0,
    }
