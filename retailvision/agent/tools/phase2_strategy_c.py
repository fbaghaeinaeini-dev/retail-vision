"""Phase 2 Tool t10: Strategy C — Trajectory graph + Louvain community detection.

Builds a graph of spatial proximity between track segments, then uses
community detection to find clusters of related trajectories.
"""

import numpy as np
import networkx as nx
from loguru import logger

try:
    import community as community_louvain
except ImportError:
    community_louvain = None

from agent.models import ToolResult, ZoneCandidate
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("strategy_trajectory_graph")
def strategy_trajectory_graph(state, config) -> ToolResult:
    """t10: Graph-based zone discovery using trajectory co-location.

    1. Discretize BEV space into cells
    2. For each cell, count how many different tracks pass through
    3. Build graph: nodes=high-traffic cells, edges=same-track connections
    4. Run Louvain community detection
    5. Each community → zone candidate
    """
    df = state.raw_tracks
    if "bev_x_meters" not in df.columns:
        return ToolResult(success=False, message="BEV-calibrated tracks required")

    if community_louvain is None:
        return ToolResult(
            success=True,
            data={"n_zones": 0},
            message="python-louvain not installed, skipping trajectory graph strategy",
        )

    resolution = config.traj_resolution  # meters per cell
    weight_threshold = config.traj_edge_weight_threshold

    bev_x = df["bev_x_meters"].values
    bev_y = df["bev_y_meters"].values
    track_ids = df["track_id"].values

    # Discretize into cells
    x_min, y_min = bev_x.min(), bev_y.min()
    cell_x = ((bev_x - x_min) / resolution).astype(int)
    cell_y = ((bev_y - y_min) / resolution).astype(int)

    # Build cell → tracks mapping
    cell_tracks: dict[tuple[int, int], set[int]] = {}
    for cx, cy, tid in zip(cell_x, cell_y, track_ids):
        key = (int(cx), int(cy))
        if key not in cell_tracks:
            cell_tracks[key] = set()
        cell_tracks[key].add(int(tid))

    # Filter to cells with multiple tracks (interesting locations)
    busy_cells = {k: v for k, v in cell_tracks.items() if len(v) >= 2}

    if len(busy_cells) < 3:
        state.zone_candidates_C = []
        return ToolResult(
            success=True,
            data={"n_zones": 0},
            message="Too few busy cells for trajectory graph",
        )

    # Build graph: edges between adjacent cells that share tracks
    G = nx.Graph()
    cells = list(busy_cells.keys())

    for cell in cells:
        G.add_node(cell, n_tracks=len(busy_cells[cell]))

    for i, c1 in enumerate(cells):
        for c2 in cells[i + 1 :]:
            # Check adjacency (within 2 cells)
            if abs(c1[0] - c2[0]) <= 2 and abs(c1[1] - c2[1]) <= 2:
                # Edge weight = shared tracks
                shared = len(busy_cells[c1] & busy_cells[c2])
                if shared >= 1:
                    G.add_edge(c1, c2, weight=shared)

    # Remove weak edges
    weak_edges = [(u, v) for u, v, d in G.edges(data=True) if d["weight"] < weight_threshold]
    G.remove_edges_from(weak_edges)

    # Remove isolated nodes
    G.remove_nodes_from(list(nx.isolates(G)))

    if len(G.nodes) < 2:
        state.zone_candidates_C = []
        return ToolResult(
            success=True,
            data={"n_zones": 0},
            message="Graph too sparse for community detection",
        )

    # Louvain community detection
    partition = community_louvain.best_partition(G, random_state=42)

    communities: dict[int, list[tuple[int, int]]] = {}
    for node, comm_id in partition.items():
        if comm_id not in communities:
            communities[comm_id] = []
        communities[comm_id].append(node)

    candidates = []
    for comm_id, cell_list in communities.items():
        if len(cell_list) < 2:
            continue

        # Convert cells back to BEV meters
        pts = np.array(cell_list) * resolution + [x_min, y_min]

        centroid = pts.mean(axis=0)
        area_m2 = len(cell_list) * resolution ** 2

        if area_m2 < config.min_zone_area_m2:
            continue

        # Polygon from convex hull
        if len(pts) >= 3:
            from scipy.spatial import ConvexHull
            try:
                hull = ConvexHull(pts)
                polygon = pts[hull.vertices].tolist()
            except Exception:
                polygon = _bbox_from_points(pts)
        else:
            polygon = _bbox_from_points(pts)

        # Confidence from community strength: combine graph density + track diversity
        subgraph = G.subgraph([c for c in cell_list if c in G])
        internal_edges = subgraph.number_of_edges()
        total_possible = len(cell_list) * (len(cell_list) - 1) / 2
        modularity = internal_edges / max(total_possible, 1)
        # Track count: how many unique tracks pass through this community
        community_tracks = set()
        for c in cell_list:
            if c in busy_cells:
                community_tracks.update(busy_cells[c])
        track_score = min(len(community_tracks) / 30, 1.0)
        # Blend: graph structure + traffic volume
        confidence = min(0.4 * modularity * 2 + 0.6 * track_score, 1.0)

        candidates.append(
            ZoneCandidate(
                zone_id=f"C_{comm_id:03d}",
                polygon_bev=polygon,
                centroid_bev=centroid.tolist(),
                area_m2=area_m2,
                confidence=float(confidence),
                strategy="trajectory_graph",
                metadata={
                    "n_cells": len(cell_list),
                    "n_internal_edges": internal_edges,
                    "modularity": float(modularity),
                },
            )
        )

    state.zone_candidates_C = candidates

    return ToolResult(
        success=True,
        data={"n_zones": len(candidates), "n_communities": len(communities)},
        message=f"Strategy C: {len(candidates)} zones from {len(communities)} communities "
                f"({len(G.nodes)} nodes, {len(G.edges)} edges)",
    )


def _bbox_from_points(pts: np.ndarray) -> list:
    x_min, y_min = pts.min(axis=0) - 0.3
    x_max, y_max = pts.max(axis=0) + 0.3
    return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
