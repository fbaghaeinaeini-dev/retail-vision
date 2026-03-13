"""Phase 2 Tool t09: Strategy B — Occupancy grid + connected components.

Rasterizes track positions onto a BEV grid, identifies high-density cells,
and groups them into zone candidates using morphological operations.
"""

import cv2
import numpy as np
from loguru import logger

from agent.models import ToolResult, ZoneCandidate
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("strategy_occupancy_grid")
def strategy_occupancy_grid(state, config) -> ToolResult:
    """t09: Grid-based occupancy density analysis in BEV coordinates.

    1. Rasterize all BEV track points onto a cell grid
    2. Normalize by time to get density (visits per m² per hour)
    3. Threshold high-density cells
    4. Morphological close + open to clean noise
    5. Connected components → zone candidates
    """
    df = state.raw_tracks
    if "bev_x_meters" not in df.columns:
        return ToolResult(success=False, message="BEV-calibrated tracks required")

    cell_size = config.occupancy_grid_cell_m  # meters per cell

    bev_x = df["bev_x_meters"].values
    bev_y = df["bev_y_meters"].values

    # Determine grid bounds
    x_min, x_max = bev_x.min() - 1, bev_x.max() + 1
    y_min, y_max = bev_y.min() - 1, bev_y.max() + 1

    grid_w = int((x_max - x_min) / cell_size) + 1
    grid_h = int((y_max - y_min) / cell_size) + 1

    # Cap grid size for memory
    grid_w = min(grid_w, 2000)
    grid_h = min(grid_h, 2000)

    # Rasterize
    grid = np.zeros((grid_h, grid_w), dtype=np.float32)
    gx = np.clip(((bev_x - x_min) / cell_size).astype(int), 0, grid_w - 1)
    gy = np.clip(((bev_y - y_min) / cell_size).astype(int), 0, grid_h - 1)

    np.add.at(grid, (gy, gx), 1)

    # Normalize by duration to get density
    duration_hrs = max(state.video_duration_seconds / 3600, 1 / 3600)
    cell_area = cell_size ** 2
    density = grid / (duration_hrs * cell_area)

    # Threshold: cells above minimum density
    min_density = config.occupancy_min_density
    # Use adaptive threshold based on non-zero cells
    nonzero = density[density > 0]
    if len(nonzero) == 0:
        state.zone_candidates_B = []
        return ToolResult(success=True, data={"n_zones": 0}, message="No occupancy detected")

    threshold = max(min_density, float(np.percentile(nonzero, 70)))
    binary = (density > threshold).astype(np.uint8)

    # Morphological operations to clean up
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)

    # Connected components
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

    candidates = []
    for label_id in range(1, n_labels):  # Skip background (0)
        area_cells = stats[label_id, cv2.CC_STAT_AREA]
        area_m2 = area_cells * cell_area

        if area_m2 < config.min_zone_area_m2:
            continue

        # Extract contour for polygon
        component_mask = (labels == label_id).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            continue

        # Convert contour from grid coordinates to BEV meters
        contour = contours[0].squeeze()
        if contour.ndim == 1:
            continue  # Degenerate contour

        polygon_bev = []
        for pt in contour:
            mx = float(pt[0] * cell_size + x_min)
            my = float(pt[1] * cell_size + y_min)
            polygon_bev.append([mx, my])

        centroid_m = [
            float(centroids[label_id][0] * cell_size + x_min),
            float(centroids[label_id][1] * cell_size + y_min),
        ]

        # Confidence from density intensity
        region_density = density[labels == label_id]
        confidence = min(float(np.mean(region_density)) / (threshold * 3), 1.0)

        candidates.append(
            ZoneCandidate(
                zone_id=f"B_{label_id:03d}",
                polygon_bev=polygon_bev,
                centroid_bev=centroid_m,
                area_m2=area_m2,
                confidence=float(confidence),
                strategy="occupancy_grid",
                metadata={
                    "mean_density": float(np.mean(region_density)),
                    "max_density": float(np.max(region_density)),
                    "area_cells": int(area_cells),
                },
            )
        )

    state.zone_candidates_B = candidates

    return ToolResult(
        success=True,
        data={
            "n_zones": len(candidates),
            "grid_size": (grid_w, grid_h),
            "threshold": round(threshold, 2),
        },
        message=f"Strategy B: {len(candidates)} zones from {grid_w}x{grid_h} grid "
                f"(cell={cell_size}m, threshold={threshold:.2f})",
    )
