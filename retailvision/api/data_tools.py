"""Data query tools for the RetailVision VLM agentic loop."""

from __future__ import annotations

from datetime import time
from typing import Any

# ── Video time anchor ────────────────────────────────────────
# The analysed footage begins at this wall-clock time.
VIDEO_START_TIME = time(10, 15, 40)


# ── Metric aliases ────────────────────────────────────────────

_METRIC_ALIASES: dict[str, str] = {
    "visits": "total_visits",
    "visit": "total_visits",
    "busy": "total_visits",
    "busiest": "total_visits",
    "traffic": "total_visits",
    "popular": "total_visits",
    "visitors": "unique_visitors",
    "dwell": "avg_dwell_seconds",
    "dwell time": "avg_dwell_seconds",
    "stay": "avg_dwell_seconds",
    "time spent": "avg_dwell_seconds",
    "duration": "avg_dwell_seconds",
    "median dwell": "median_dwell_seconds",
    "p95 dwell": "p95_dwell_seconds",
    "density": "density_people_per_m2_hr",
    "crowded": "density_people_per_m2_hr",
    "occupancy": "avg_occupancy",
    "return": "return_rate",
    "return rate": "return_rate",
    "area": "area_m2",
}

_ANALYTICS_METRICS = {
    "total_visits",
    "unique_visitors",
    "avg_dwell_seconds",
    "median_dwell_seconds",
    "p95_dwell_seconds",
    "avg_occupancy",
    "max_occupancy",
    "return_rate",
    "density_people_per_m2_hr",
}


def _resolve_metric(text: str) -> str:
    """Resolve a human-readable metric name to its report key."""
    text_lower = text.lower().strip()
    if text_lower in _ANALYTICS_METRICS or text_lower == "area_m2":
        return text_lower
    return _METRIC_ALIASES.get(text_lower, "total_visits")


def _zone_label(zone: dict) -> str:
    """Get a display label for a zone.

    Falls back to a short description extract when business_name is
    "Unknown" or missing.
    """
    name = zone.get("business_name", "")
    # If the name is usable, return it
    if name and not name.lower().startswith("unknown"):
        return name

    # Try deriving a name from the description
    desc = zone.get("description", "")
    if desc:
        return _name_from_description(desc, zone.get("zone_type", ""))

    # Fall back to zone_type or zone_id
    ztype = zone.get("zone_type", "")
    if ztype and ztype != "unknown":
        return ztype.replace("_", " ").title()
    return zone.get("zone_id", "Unknown")


def _name_from_description(desc: str, zone_type: str) -> str:
    """Extract a short name from a zone description."""
    # Take first sentence, trim to a reasonable label
    first_sentence = desc.split(".")[0].strip()
    # Remove common prefixes like "This zone functions as a"
    for prefix in [
        "this zone functions as ",
        "this zone serves as ",
        "this zone is ",
        "this zone operates as ",
        "classified as ",
        "sign for ",
    ]:
        if first_sentence.lower().startswith(prefix):
            first_sentence = first_sentence[len(prefix):]
            break
    # Remove leading articles
    for article in ["a ", "an ", "the "]:
        if first_sentence.lower().startswith(article):
            first_sentence = first_sentence[len(article):]
            break
    # Cap length
    if len(first_sentence) > 30:
        first_sentence = first_sentence[:27] + "..."
    return first_sentence[:1].upper() + first_sentence[1:] if first_sentence else zone_type.replace("_", " ").title()


# ── Data formatting for VLM system prompt ─────────────────────

def get_full_data_context(report: dict) -> str:
    """Format a lightweight overview of report data for VLM system prompt.

    Only includes zone names, IDs, types, and aggregate stats.
    The VLM must call tools (query_zones, get_zone_detail, etc.)
    to get actual metric values — this keeps the prompt small and
    forces tool use for data-dependent answers.
    """
    parts: list[str] = []

    # Meta
    meta = report.get("meta", {})
    if meta:
        parts.append(
            f"Video: {meta.get('video_id', 'unknown')} | "
            f"scene: {meta.get('scene_type', 'unknown')} | "
            f"start: {VIDEO_START_TIME.strftime('%H:%M:%S')} | "
            f"duration: {meta.get('duration_seconds', 0):.0f}s (30 min)"
        )

    # Summary stats
    stats = get_summary_stats(report)
    parts.append(
        f"\nSummary: {stats['total_zones']} zones, "
        f"{stats['total_visits']} total visits, "
        f"avg dwell {stats['avg_dwell']:.1f}s, "
        f"busiest zone: {stats['busiest_zone_name']} ({stats['busiest_zone_visits']} visits)"
    )

    # Zone directory — names, IDs, and types only (no metrics)
    zones = report.get("zones", {})
    parts.append(f"\n=== ZONE DIRECTORY ({len(zones)}) ===")
    parts.append("Use query_zones tool to get actual metric values.")

    for zid, z in zones.items():
        parts.append(
            f"  {zid}: {_zone_label(z)} ({z.get('zone_type', '?')})"
        )

    # Flow availability hint
    flow = report.get("flow", {})
    transitions = flow.get("transitions", [])
    if transitions:
        parts.append(f"\nFlow data available: {len(transitions)} transitions. Use get_flow_data tool.")

    return "\n".join(parts) if parts else "No report data available."


# ── Query tools ───────────────────────────────────────────────

def query_zones(
    report: dict,
    sort_by: str = "total_visits",
    order: str = "desc",
    limit: int | None = None,
    zone_type: str | None = None,
) -> list[dict]:
    """Query zones with sorting, filtering, limiting.

    Returns list of dicts with zone_id, name, type, and all metrics.
    """
    zones = report.get("zones", {})
    analytics = report.get("analytics", {})
    results: list[dict] = []

    for zid, z in zones.items():
        m = analytics.get(zid, {})

        # Filter by zone_type
        if zone_type and z.get("zone_type", "").lower() != zone_type.lower():
            continue

        entry = {
            "zone_id": zid,
            "name": _zone_label(z),
            "zone_type": z.get("zone_type", "unknown"),
            "area_m2": z.get("area_m2", 0),
        }
        # Merge all analytics
        for key in _ANALYTICS_METRICS:
            entry[key] = m.get(key, 0)

        results.append(entry)

    # Resolve sort metric
    sort_key = _resolve_metric(sort_by) if sort_by not in _ANALYTICS_METRICS | {"area_m2"} else sort_by
    reverse = order.lower() != "asc"
    results.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse)

    if limit is not None and limit > 0:
        results = results[:limit]

    return results


def get_zone_detail(report: dict, zone_id: str) -> dict | None:
    """Get comprehensive detail for a zone.

    Returns metrics, description, polygon_pixel, polygon_bev, bbox.
    """
    zones = report.get("zones", {})
    analytics = report.get("analytics", {})

    z = zones.get(zone_id)
    if z is None:
        return None

    m = analytics.get(zone_id, {})

    detail = {
        "zone_id": zone_id,
        "name": _zone_label(z),
        "zone_type": z.get("zone_type", "unknown"),
        "description": z.get("description", ""),
        "vlm_confidence": z.get("vlm_confidence", 0),
        "area_m2": z.get("area_m2", 0),
        "polygon_bev": z.get("polygon_bev", []),
        "polygon_pixel": z.get("polygon_pixel", []),
        "centroid_bev": z.get("centroid_bev", []),
        "bbox_pixel": z.get("bbox_pixel", []),
        "depth_info": z.get("depth_info", {}),
        "objects": z.get("objects", []),
        "signage": z.get("signage", {}),
        "strategy_agreement": z.get("strategy_agreement", 0),
        "contributing_strategies": z.get("contributing_strategies", []),
    }
    # Merge analytics
    for key in _ANALYTICS_METRICS:
        detail[key] = m.get(key, 0)

    return detail


def get_top_zones(report: dict, metric: str, n: int = 3) -> list[dict]:
    """Get top N zones by a given metric.

    Returns sorted list with zone_id, label (name), value, and all metrics.
    """
    resolved = _resolve_metric(metric)
    all_zones = query_zones(report, sort_by=resolved, order="desc")

    results = []
    for z in all_zones[:n]:
        entry = dict(z)
        entry["label"] = z["name"]
        entry["value"] = z.get(resolved, 0)
        results.append(entry)

    return results


def search_zones_by_name(report: dict, query: str) -> list[dict]:
    """Find zones whose business_name contains query (case-insensitive)."""
    zones = report.get("zones", {})
    analytics = report.get("analytics", {})
    query_lower = query.lower()
    results = []

    for zid, z in zones.items():
        name = _zone_label(z)
        if query_lower in name.lower():
            m = analytics.get(zid, {})
            entry = {
                "zone_id": zid,
                "name": name,
                "zone_type": z.get("zone_type", "unknown"),
                "area_m2": z.get("area_m2", 0),
            }
            for key in _ANALYTICS_METRICS:
                entry[key] = m.get(key, 0)
            results.append(entry)

    return results


def get_flow_data(report: dict, zone_id: str | None = None) -> dict:
    """Get flow transitions, optionally filtered to/from a specific zone."""
    flow = report.get("flow", {})
    transitions = flow.get("transitions", [])
    top_paths = flow.get("top_paths", [])

    if zone_id:
        filtered = [
            t for t in transitions
            if t.get("from_zone") == zone_id or t.get("to_zone") == zone_id
        ]
        filtered_paths = [
            p for p in top_paths
            if p.get("from_zone", p.get("from")) == zone_id
            or p.get("to_zone", p.get("to")) == zone_id
        ]
        return {"transitions": filtered, "top_paths": filtered_paths}

    return {"transitions": transitions, "top_paths": top_paths}


def get_summary_stats(report: dict) -> dict:
    """Get aggregate summary stats."""
    zones = report.get("zones", {})
    analytics = report.get("analytics", {})

    total_visits = sum(a.get("total_visits", 0) for a in analytics.values())
    dwells = [a.get("avg_dwell_seconds", 0) for a in analytics.values() if a.get("avg_dwell_seconds", 0) > 0]
    avg_dwell = sum(dwells) / len(dwells) if dwells else 0.0
    total_zones = len(zones)

    # Busiest zone
    busiest_id = max(analytics, key=lambda k: analytics[k].get("total_visits", 0)) if analytics else ""
    busiest_visits = analytics.get(busiest_id, {}).get("total_visits", 0) if busiest_id else 0
    busiest_name = _zone_label(zones.get(busiest_id, {})) if busiest_id else "N/A"

    # Zone types breakdown
    type_counts: dict[str, int] = {}
    for z in zones.values():
        zt = z.get("zone_type", "unknown")
        type_counts[zt] = type_counts.get(zt, 0) + 1

    return {
        "total_zones": total_zones,
        "total_visits": total_visits,
        "avg_dwell": avg_dwell,
        "busiest_zone_id": busiest_id,
        "busiest_zone_name": busiest_name,
        "busiest_zone_visits": busiest_visits,
        "zone_type_counts": type_counts,
    }
