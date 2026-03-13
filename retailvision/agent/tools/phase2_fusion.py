"""Phase 2 Tool t11: Ensemble zone fusion with weighted spatial voting.

Combines zone candidates from all 3 strategies using a voting grid.
Zones agreed upon by 2+ strategies are strong; single-strategy zones
need high confidence to survive.
"""

import cv2
import numpy as np
from loguru import logger

from agent.models import FusedZone, ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("fuse_zone_candidates")
def fuse_zone_candidates(state, config) -> ToolResult:
    """t11: Ensemble fusion via spatial voting grid.

    1. Create voting grid at 4x BEV resolution
    2. Rasterize each candidate polygon, weighted by confidence
    3. Per cell: count strategies with vote > 0.1
    4. STRONG zone: >= 2 strategies agree
       WEAK zone: 1 strategy but confidence > 0.7
    5. Morphological close(5x5) + open(3x3)
    6. Connected components → final zones
    7. Filter by min_zone_area_m2
    """
    all_candidates = (
        state.zone_candidates_A +
        state.zone_candidates_B +
        state.zone_candidates_C
    )

    if not all_candidates:
        state.fused_zones = []
        state.fused_zones_dict = {}
        return ToolResult(
            success=True,
            data={"n_fused_zones": 0},
            message="No zone candidates to fuse",
        )

    # Determine bounds from all candidates
    all_pts = []
    for c in all_candidates:
        all_pts.extend(c.polygon_bev)
    all_pts = np.array(all_pts)
    x_min, y_min = all_pts.min(axis=0) - 2
    x_max, y_max = all_pts.max(axis=0) + 2

    # Voting grid at higher resolution
    vote_resolution = state.bev_scale * 4 if state.bev_scale > 0 else 0.2
    grid_w = int((x_max - x_min) / vote_resolution) + 1
    grid_h = int((y_max - y_min) / vote_resolution) + 1
    grid_w = min(grid_w, 2000)
    grid_h = min(grid_h, 2000)

    # Per-strategy vote grids
    strategy_grids = {"dwell_clustering": None, "occupancy_grid": None, "trajectory_graph": None}
    for strategy in strategy_grids:
        strategy_grids[strategy] = np.zeros((grid_h, grid_w), dtype=np.float32)

    # Rasterize each candidate
    for candidate in all_candidates:
        polygon = np.array(candidate.polygon_bev)
        # Convert to grid coordinates
        grid_pts = ((polygon - [x_min, y_min]) / vote_resolution).astype(np.int32)
        grid_pts = grid_pts.reshape((-1, 1, 2))

        mask = np.zeros((grid_h, grid_w), dtype=np.uint8)
        cv2.fillPoly(mask, [grid_pts], 1)

        strategy_grids[candidate.strategy] += mask * candidate.confidence

    # Count agreeing strategies per cell
    agreement_grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
    confidence_grid = np.zeros((grid_h, grid_w), dtype=np.float32)

    for strategy, grid in strategy_grids.items():
        agreement_grid += (grid > 0.1).astype(np.uint8)
        confidence_grid += grid

    # Apply fusion rules — adaptive when some strategies produce nothing
    active_strategies = sum(1 for g in strategy_grids.values() if g.max() > 0.1)
    min_strategies = config.fusion_min_strategies
    min_single_conf = config.fusion_single_strategy_min_conf

    # When only 2 strategies produce output, lower thresholds modestly —
    # too aggressive a drop causes Strategy C hulls to tile the entire scene
    if active_strategies <= 2 and min_strategies > 1:
        min_single_conf = max(0.55, min_single_conf * 0.8)
        logger.info(f"Adaptive fusion: {active_strategies} active strategies, "
                   f"single-strategy threshold = {min_single_conf:.2f}")

    strong = agreement_grid >= min_strategies
    weak = (agreement_grid == 1) & (confidence_grid > min_single_conf)
    fused_binary = (strong | weak).astype(np.uint8)

    # Morphological cleanup — small kernels to avoid merging nearby zones
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fused_binary = cv2.morphologyEx(fused_binary, cv2.MORPH_CLOSE, kernel_close)
    fused_binary = cv2.morphologyEx(fused_binary, cv2.MORPH_OPEN, kernel_open)

    # Connected components
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        fused_binary, connectivity=8
    )

    # Post-fusion: split oversized zones using watershed on confidence peaks
    max_zone_area_m2 = config.max_zone_area_m2
    labels, n_labels, stats, centroids = _split_oversized_zones(
        labels, n_labels, stats, centroids, confidence_grid,
        vote_resolution, max_zone_area_m2,
    )

    fused_zones = []
    fused_zones_dict = {}

    for label_id in range(1, n_labels):
        area_cells = stats[label_id, cv2.CC_STAT_AREA]
        area_m2 = area_cells * vote_resolution ** 2

        if area_m2 < config.min_zone_area_m2:
            continue

        # Extract contour
        component_mask = (labels == label_id).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            continue

        contour = contours[0].squeeze()
        if contour.ndim == 1:
            continue

        # Convert to BEV meters
        polygon_bev = []
        for pt in contour:
            mx = float(pt[0] * vote_resolution + x_min)
            my = float(pt[1] * vote_resolution + y_min)
            polygon_bev.append([mx, my])

        centroid_bev = [
            float(centroids[label_id][0] * vote_resolution + x_min),
            float(centroids[label_id][1] * vote_resolution + y_min),
        ]

        # Determine which strategies contributed
        region_mask = labels == label_id
        contributing = []
        for strategy, grid in strategy_grids.items():
            if (grid[region_mask] > 0.1).any():
                contributing.append(strategy)

        zone_agreement = len(contributing)
        region_conf = float(confidence_grid[region_mask].mean())

        # Compute pixel bbox via inverse homography
        bbox_pixel = _bev_polygon_to_pixel_bbox(polygon_bev, state)

        zone_id = f"zone_{len(fused_zones) + 1:03d}"
        zone = FusedZone(
            zone_id=zone_id,
            polygon_bev=polygon_bev,
            centroid_bev=centroid_bev,
            area_m2=area_m2,
            bbox_pixel=bbox_pixel,
            strategy_agreement=zone_agreement,
            contributing_strategies=contributing,
            confidence=region_conf,
        )
        fused_zones.append(zone)
        fused_zones_dict[zone_id] = {
            "zone_id": zone_id,
            "polygon_bev": polygon_bev,
            "centroid_bev": centroid_bev,
            "area_m2": area_m2,
            "bbox_pixel": bbox_pixel,
            "strategy_agreement": zone_agreement,
            "contributing_strategies": contributing,
        }

    # Post-fusion: merge small zones into nearest larger neighbor
    merge_threshold_m2 = config.merge_threshold_m2
    merge_max_distance_m = config.merge_max_distance_m
    fused_zones, fused_zones_dict = _merge_small_zones(
        fused_zones, fused_zones_dict, merge_threshold_m2, merge_max_distance_m,
    )

    state.fused_zones = fused_zones
    state.fused_zones_dict = fused_zones_dict

    # Also create a draft registry for Phase 3 depth analysis
    state.zone_registry_draft = fused_zones_dict

    return ToolResult(
        success=True,
        data={
            "n_fused_zones": len(fused_zones),
            "n_candidates_A": len(state.zone_candidates_A),
            "n_candidates_B": len(state.zone_candidates_B),
            "n_candidates_C": len(state.zone_candidates_C),
        },
        message=f"Fused {len(fused_zones)} zones from "
                f"A={len(state.zone_candidates_A)}, "
                f"B={len(state.zone_candidates_B)}, "
                f"C={len(state.zone_candidates_C)} candidates",
    )


def _split_oversized_zones(labels, n_labels, stats, centroids,
                           confidence_grid, vote_resolution, max_area_m2):
    """Split any connected component exceeding max_area_m2 using watershed.

    Uses local maxima in the confidence grid as seeds, then watershed
    to assign pixels to the nearest peak — producing natural sub-zones.
    """
    from scipy import ndimage

    changed = False
    next_label = n_labels

    for label_id in range(1, n_labels):
        area_cells = stats[label_id, cv2.CC_STAT_AREA]
        area_m2 = area_cells * vote_resolution ** 2

        if area_m2 <= max_area_m2:
            continue

        component_mask = (labels == label_id).astype(np.uint8)
        conf_in_region = confidence_grid * component_mask.astype(np.float32)

        # Find local maxima as watershed seeds
        blurred = cv2.GaussianBlur(conf_in_region, (7, 7), 0)
        dilated = cv2.dilate(blurred, np.ones((9, 9)), iterations=1)
        local_max = (blurred == dilated) & (blurred > 0.2) & (component_mask > 0)

        seed_labels, n_seeds = ndimage.label(local_max)

        if n_seeds <= 1:
            continue

        logger.info(f"Splitting oversized zone (label={label_id}, "
                   f"area={area_m2:.0f}m²) into {n_seeds} sub-zones via watershed")

        # Watershed: markers with shifted label IDs
        markers = seed_labels.copy().astype(np.int32)
        markers[markers > 0] += next_label - 1
        # Outside component = 0 (unknown), let watershed assign
        markers[component_mask == 0] = 0

        dist_img = (blurred * 255).astype(np.uint8)
        dist_3ch = cv2.cvtColor(dist_img, cv2.COLOR_GRAY2BGR)
        cv2.watershed(dist_3ch, markers)

        # Assign watershed results back into labels array
        # Watershed marks boundaries as -1; assign those to nearest seed
        for seed_id in range(1, n_seeds + 1):
            new_label = next_label + seed_id - 1
            sub_mask = (markers == new_label) & (component_mask > 0)
            if sub_mask.any():
                labels[sub_mask] = new_label

        # Boundary pixels (-1) stay as original label_id — assign to 0 (remove)
        boundary_mask = (markers == -1) & (component_mask > 0)
        labels[boundary_mask] = 0

        next_label += n_seeds
        changed = True

    if not changed:
        return labels, n_labels, stats, centroids

    # Recompute stats directly from the modified labels (NOT from binary)
    unique_labels = np.unique(labels)
    unique_labels = unique_labels[unique_labels > 0]  # exclude background

    # Rebuild stats array: [x, y, w, h, area] per label
    new_n_labels = len(unique_labels) + 1  # +1 for background
    new_stats = np.zeros((new_n_labels, 5), dtype=np.int32)
    new_centroids = np.zeros((new_n_labels, 2), dtype=np.float64)

    # Relabel to sequential IDs
    new_labels = np.zeros_like(labels)
    for new_id, old_id in enumerate(unique_labels, start=1):
        mask = labels == old_id
        new_labels[mask] = new_id
        ys, xs = np.where(mask)
        if len(xs) > 0:
            new_stats[new_id, cv2.CC_STAT_LEFT] = xs.min()
            new_stats[new_id, cv2.CC_STAT_TOP] = ys.min()
            new_stats[new_id, cv2.CC_STAT_WIDTH] = xs.max() - xs.min() + 1
            new_stats[new_id, cv2.CC_STAT_HEIGHT] = ys.max() - ys.min() + 1
            new_stats[new_id, cv2.CC_STAT_AREA] = len(xs)
            new_centroids[new_id] = [xs.mean(), ys.mean()]

    return new_labels, new_n_labels, new_stats, new_centroids


def _merge_small_zones(
    fused_zones: list,
    fused_zones_dict: dict,
    merge_threshold_m2: float,
    merge_max_distance_m: float,
) -> tuple[list, dict]:
    """Merge zones smaller than threshold into their nearest larger neighbor.

    For each small zone, find the closest large zone (by centroid distance).
    If within merge_max_distance_m, absorb the small zone:
      - Expand polygon to convex hull of both
      - Recalculate centroid and area
      - Union contributing strategies
    """
    if len(fused_zones) < 2:
        return fused_zones, fused_zones_dict

    small = [z for z in fused_zones if z.area_m2 < merge_threshold_m2]
    large = [z for z in fused_zones if z.area_m2 >= merge_threshold_m2]

    if not small or not large:
        return fused_zones, fused_zones_dict

    merged_into = {}  # small zone_id → large zone_id

    for sz in small:
        sc = np.array(sz.centroid_bev)
        best_dist = float("inf")
        best_target = None

        for lz in large:
            dist = np.linalg.norm(sc - np.array(lz.centroid_bev))
            if dist < best_dist:
                best_dist = dist
                best_target = lz

        if best_target is not None and best_dist <= merge_max_distance_m:
            merged_into[sz.zone_id] = best_target.zone_id
            logger.info(
                f"Merging {sz.zone_id} ({sz.area_m2:.1f}m²) → "
                f"{best_target.zone_id} (dist={best_dist:.1f}m)"
            )

            # Expand polygon via convex hull
            all_pts = np.array(best_target.polygon_bev + sz.polygon_bev)
            hull = cv2.convexHull(all_pts.astype(np.float32))
            best_target.polygon_bev = hull.squeeze().tolist()

            # Recalculate centroid (area-weighted)
            total_area = best_target.area_m2 + sz.area_m2
            cx = (best_target.centroid_bev[0] * best_target.area_m2 +
                  sz.centroid_bev[0] * sz.area_m2) / total_area
            cy = (best_target.centroid_bev[1] * best_target.area_m2 +
                  sz.centroid_bev[1] * sz.area_m2) / total_area
            best_target.centroid_bev = [cx, cy]
            best_target.area_m2 = total_area

            # Union strategies
            for s in sz.contributing_strategies:
                if s not in best_target.contributing_strategies:
                    best_target.contributing_strategies.append(s)
            best_target.strategy_agreement = len(best_target.contributing_strategies)

    # Rebuild lists excluding merged-away zones
    merged_ids = set(merged_into.keys())
    result_zones = [z for z in fused_zones if z.zone_id not in merged_ids]

    # Re-number zone IDs sequentially and rebuild dict
    result_dict = {}
    for i, z in enumerate(result_zones):
        new_id = f"zone_{i + 1:03d}"
        z.zone_id = new_id
        result_dict[new_id] = {
            "zone_id": new_id,
            "polygon_bev": z.polygon_bev,
            "centroid_bev": z.centroid_bev,
            "area_m2": z.area_m2,
            "bbox_pixel": z.bbox_pixel,
            "strategy_agreement": z.strategy_agreement,
            "contributing_strategies": z.contributing_strategies,
        }

    logger.info(f"Zone merging: {len(fused_zones)} → {len(result_zones)} "
               f"({len(merged_ids)} small zones absorbed)")

    return result_zones, result_dict


def _bev_polygon_to_pixel_bbox(polygon_bev, state) -> list[float]:
    """Convert BEV polygon back to pixel bounding box."""
    if state.homography_matrix is None:
        return [0, 0, 100, 100]

    H_inv = np.linalg.inv(state.homography_matrix)
    bev_resolution = state.bev_scale

    pts_bev = np.array(polygon_bev) / bev_resolution  # BEV meters → BEV pixels
    pts_h = np.hstack([pts_bev, np.ones((len(pts_bev), 1))])
    pts_pixel = (H_inv @ pts_h.T).T
    pts_pixel = pts_pixel[:, :2] / pts_pixel[:, 2:3]

    x1 = float(pts_pixel[:, 0].min())
    y1 = float(pts_pixel[:, 1].min())
    x2 = float(pts_pixel[:, 0].max())
    y2 = float(pts_pixel[:, 1].max())

    # Clamp to frame bounds
    H_img, W_img = state.frame_shape[:2]
    x1 = max(0, min(x1, W_img))
    y1 = max(0, min(y1, H_img))
    x2 = max(0, min(x2, W_img))
    y2 = max(0, min(y2, H_img))

    return [x1, y1, x2, y2]
