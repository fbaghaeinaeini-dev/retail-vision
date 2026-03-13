"""Phase 5 Tools: t24 (validate_zones) and t25 (quality_gate).

Validates zone quality using silhouette score, coverage, temporal stability,
and VLM confidence. Quality gate can trigger Phase 2 re-run.
"""

import numpy as np
from loguru import logger
from sklearn.metrics import silhouette_score

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("validate_zones")
def validate_zones(state, config) -> ToolResult:
    """t24: Compute validation metrics for discovered zones.

    Metrics:
    - silhouette_score: cluster separation quality [-1, 1]
    - coverage_pct: what % of dwell points fall within zones
    - temporal_stability: consistency of zones across time windows
    - vlm_agreement: average VLM classification confidence
    - zone_count_sanity: reasonable number of zones for scene type
    """
    registry = state.zone_registry
    if not registry:
        state.validation_metrics = {"overall_score": 0}
        return ToolResult(
            success=True,
            data={"overall_score": 0},
            message="No zones to validate",
        )

    metrics = {}

    # 1. Silhouette score on dwell points
    if state.dwell_points and len(registry) >= 2:
        metrics["silhouette"] = _compute_silhouette(state)
    else:
        metrics["silhouette"] = 0.5  # Neutral if can't compute

    # 2. Coverage: % of dwell points within zones
    metrics["coverage_pct"] = _compute_coverage(state)

    # 3. VLM agreement: average classification confidence
    confidences = [z.get("vlm_confidence", 0) for z in registry.values()]
    metrics["vlm_agreement"] = float(np.mean(confidences)) if confidences else 0

    # 4. Zone count sanity — dynamic, no hardcoded scene-type expectations
    n_zones = len(registry)
    n_dwell = len(state.dwell_points) if state.dwell_points else 0
    # Heuristic: expect roughly 1 zone per 10-50 dwell points, clamped to [2, 30]
    if n_dwell > 0:
        lo = max(2, n_dwell // 50)
        hi = max(lo + 3, min(30, n_dwell // 10))
    else:
        lo, hi = 2, 15
    if lo <= n_zones <= hi:
        metrics["count_sanity"] = 1.0
    elif n_zones < lo:
        metrics["count_sanity"] = max(0.3, n_zones / lo)
    else:
        metrics["count_sanity"] = max(0, 1 - (n_zones - hi) / 10)

    # 5. Strategy agreement: how many zones have 2+ strategies
    agreements = [z.get("strategy_agreement", 0) for z in registry.values()]
    metrics["multi_strategy_pct"] = sum(1 for a in agreements if a >= 2) / max(len(agreements), 1)

    # Overall weighted score
    overall = (
        0.25 * max(0, metrics["silhouette"]) +
        0.20 * metrics["coverage_pct"] +
        0.20 * metrics["vlm_agreement"] +
        0.15 * metrics["count_sanity"] +
        0.20 * metrics["multi_strategy_pct"]
    )
    metrics["overall_score"] = float(overall)

    state.validation_metrics = metrics

    return ToolResult(
        success=True,
        data=metrics,
        message=f"Validation: overall={overall:.2f} (silhouette={metrics['silhouette']:.2f}, "
                f"coverage={metrics['coverage_pct']:.0%}, vlm={metrics['vlm_agreement']:.2f})",
    )


@ToolRegistry.register("quality_gate")
def quality_gate(state, config) -> ToolResult:
    """t25: Quality gate — pass/fail decision and potential Phase 2 re-run.

    If overall score < threshold AND retries available, triggers re-run
    with relaxed parameters.
    """
    overall = state.validation_metrics.get("overall_score", 0)
    threshold = config.quality_threshold

    if overall >= threshold:
        state.quality_passed = True
        return ToolResult(
            success=True,
            data={"passed": True, "score": overall, "threshold": threshold, "retry": False},
            message=f"Quality gate PASSED: {overall:.2f} >= {threshold:.2f}",
        )
    else:
        can_retry = state.phase2_retry_count < 2
        state.quality_passed = not can_retry  # Accept if no retries left

        return ToolResult(
            success=True,
            data={
                "passed": False,
                "score": overall,
                "threshold": threshold,
                "retry": can_retry,
            },
            message=f"Quality gate {'RETRY' if can_retry else 'ACCEPT (no retries left)'}: "
                    f"{overall:.2f} < {threshold:.2f}",
        )


def _compute_silhouette(state) -> float:
    """Compute silhouette score for dwell point clustering."""
    from shapely.geometry import Point, Polygon

    dwell_pts = np.array([d.centroid_bev for d in state.dwell_points])
    if len(dwell_pts) < 4:
        return 0.5

    # Assign each dwell point to nearest zone
    zone_polys = {}
    for zid, zone in state.zone_registry.items():
        poly_pts = zone.get("polygon_bev", [])
        if len(poly_pts) >= 3:
            try:
                zone_polys[zid] = Polygon(poly_pts)
            except Exception:
                continue

    labels = []
    valid_pts = []
    zone_ids = list(zone_polys.keys())

    for pt in dwell_pts:
        p = Point(pt)
        assigned = -1
        min_dist = float("inf")
        for i, zid in enumerate(zone_ids):
            d = zone_polys[zid].distance(p)
            if d < min_dist:
                min_dist = d
                assigned = i
        labels.append(assigned)
        valid_pts.append(pt)

    labels = np.array(labels)
    valid_pts = np.array(valid_pts)

    if len(set(labels)) < 2:
        return 0.5

    try:
        return float(silhouette_score(valid_pts, labels))
    except Exception:
        return 0.5


def _compute_coverage(state) -> float:
    """Compute what fraction of dwell points fall within discovered zones."""
    from shapely.geometry import Point, Polygon

    if not state.dwell_points:
        return 0.0

    zone_polys = []
    for zid, zone in state.zone_registry.items():
        poly_pts = zone.get("polygon_bev", [])
        if len(poly_pts) >= 3:
            try:
                zone_polys.append(Polygon(poly_pts))
            except Exception:
                continue

    if not zone_polys:
        return 0.0

    covered = 0
    for d in state.dwell_points:
        pt = Point(d.centroid_bev)
        if any(poly.contains(pt) or poly.distance(pt) < 0.5 for poly in zone_polys):
            covered += 1

    return covered / len(state.dwell_points)
