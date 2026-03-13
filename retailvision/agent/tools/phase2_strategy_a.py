"""Phase 2 Tool t08: Strategy A — Dwell-point clustering with ST-DBSCAN.

Clusters dwell points in space-time using a spatio-temporal DBSCAN variant.
Produces zone candidates based on where people frequently stop.
"""

import numpy as np
from loguru import logger
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import DBSCAN

from agent.models import ToolResult, ZoneCandidate
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("strategy_dwell_clustering")
def strategy_dwell_clustering(state, config) -> ToolResult:
    """t08: Cluster dwell points using spatial DBSCAN in BEV coordinates.

    Uses spatial distance with scene-adaptive eps parameter.
    Temporal proximity is implicit since dwell points already represent
    significant dwelling events.
    """
    if not state.dwell_points:
        state.zone_candidates_A = []
        return ToolResult(
            success=True,
            data={"n_clusters": 0},
            message="No dwell points to cluster",
        )

    # Extract dwell centroids in BEV meters
    points = np.array([d.centroid_bev for d in state.dwell_points])
    durations = np.array([d.duration_seconds for d in state.dwell_points])

    eps = config.stdbscan_spatial_eps_m
    # Adaptive min_samples: lower when few dwell points
    min_samples = min(config.stdbscan_min_samples, max(2, len(points) // 5))

    # Run DBSCAN on spatial coordinates
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean")
    labels = clustering.fit_predict(points)

    unique_labels = set(labels) - {-1}
    candidates = []

    for label in unique_labels:
        mask = labels == label
        cluster_pts = points[mask]
        cluster_durs = durations[mask]

        centroid = cluster_pts.mean(axis=0)

        # Compute convex hull polygon
        if len(cluster_pts) >= 3:
            from scipy.spatial import ConvexHull
            try:
                hull = ConvexHull(cluster_pts)
                polygon = cluster_pts[hull.vertices].tolist()
                area = float(hull.volume)  # In 2D, volume = area
            except Exception:
                # Degenerate hull — use bounding box
                polygon, area = _bbox_polygon(cluster_pts)
        else:
            polygon, area = _bbox_polygon(cluster_pts)

        if area < config.min_zone_area_m2:
            continue

        # Confidence based on cluster size and dwell time
        size_score = min(mask.sum() / 20, 1.0)
        dwell_score = min(cluster_durs.mean() / 60, 1.0)
        confidence = 0.6 * size_score + 0.4 * dwell_score

        candidates.append(
            ZoneCandidate(
                zone_id=f"A_{label:03d}",
                polygon_bev=polygon,
                centroid_bev=centroid.tolist(),
                area_m2=area,
                confidence=float(confidence),
                strategy="dwell_clustering",
                metadata={
                    "n_dwell_points": int(mask.sum()),
                    "avg_dwell_seconds": float(cluster_durs.mean()),
                },
            )
        )

    state.zone_candidates_A = candidates

    return ToolResult(
        success=True,
        data={"n_clusters": len(candidates), "noise_points": int((labels == -1).sum())},
        message=f"Strategy A: {len(candidates)} clusters from {len(points)} dwell points "
                f"(eps={eps}m, min_samples={min_samples})",
    )


def _bbox_polygon(points: np.ndarray) -> tuple[list, float]:
    """Create a bounding box polygon from points."""
    x_min, y_min = points.min(axis=0)
    x_max, y_max = points.max(axis=0)
    # Add small padding
    pad = 0.3
    polygon = [
        [x_min - pad, y_min - pad],
        [x_max + pad, y_min - pad],
        [x_max + pad, y_max + pad],
        [x_min - pad, y_max + pad],
    ]
    area = (x_max - x_min + 2 * pad) * (y_max - y_min + 2 * pad)
    return polygon, float(area)
