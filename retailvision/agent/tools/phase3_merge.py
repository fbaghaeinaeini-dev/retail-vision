"""Phase 3 Tool t19: Merge all zone data into final ZoneRegistry.

Zone types are free-form strings from VLM — no normalization or enum constraints.
"""

import numpy as np
from loguru import logger
from shapely.geometry import Polygon as ShapelyPolygon, box as shapely_box

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("merge_zone_registry")
def merge_zone_registry(state, config) -> ToolResult:
    """t19: Combine all Phase 2-3 data into the final zone registry.

    Zone types pass through as-is from VLM classification — no normalization.
    """
    registry = {}

    for zone in state.fused_zones:
        zid = zone.zone_id

        # Gather all VLM data
        objects = state.zone_objects.get(zid, [])
        signage = state.zone_signage.get(zid, {})
        classification = state.zone_classifications.get(zid, {})
        description = state.zone_descriptions.get(zid, "")
        depth_info = state.zone_depth_info.get(zid, {})

        # Determine business name
        business_name = (
            signage.get("primary_business_name")
            or classification.get("suggested_name")
            or _generate_zone_name(classification.get("zone_type", "unknown"), zid)
        )

        # VLM-decided zone type — pass through as-is, no normalization
        zone_type = classification.get("zone_type", "unknown")

        # Compute pixel polygon from BEV polygon
        polygon_pixel = _project_bev_to_pixel(zone.polygon_bev, state)

        # Derive bbox_pixel from the fresh polygon_pixel
        if polygon_pixel and len(polygon_pixel) >= 3:
            pp = np.array(polygon_pixel)
            bbox_pixel = [float(pp[:, 0].min()), float(pp[:, 1].min()),
                          float(pp[:, 0].max()), float(pp[:, 1].max())]
        else:
            bbox_pixel = zone.bbox_pixel

        registry[zid] = {
            "zone_id": zid,
            "business_name": business_name,
            "zone_type": zone_type,
            "vlm_confidence": classification.get("confidence", 0.0),
            "description": description,
            "polygon_bev": zone.polygon_bev,
            "polygon_pixel": polygon_pixel,
            "centroid_bev": zone.centroid_bev,
            "area_m2": zone.area_m2,
            "bbox_pixel": bbox_pixel,
            "depth_info": depth_info,
            "objects": objects,
            "signage": signage,
            "strategy_agreement": zone.strategy_agreement,
            "contributing_strategies": zone.contributing_strategies,
        }

    # Merge static structures that don't overlap with movement zones
    for structure in state.static_structures:
        overlaps = _find_overlapping_zone(structure, registry, state)
        if overlaps:
            registry[overlaps].setdefault("structures_detected", [])
            registry[overlaps]["structures_detected"].append(structure)
        else:
            new_id = f"zone_{len(registry) + 1:03d}"
            registry[new_id] = _create_zone_from_structure(new_id, structure, state)

    # De-duplicate names
    _deduplicate_names(registry)

    state.zone_registry = registry

    return ToolResult(
        success=True,
        data={"total_zones": len(registry)},
        message=f"Final registry: {len(registry)} zones",
    )


def _generate_zone_name(zone_type: str, zone_id: str) -> str:
    """Generate a descriptive name from any zone type string."""
    label = zone_type.replace("_", " ").title()
    suffix = zone_id.split("_")[-1]
    return f"{label} {suffix}"


def _project_bev_to_pixel(polygon_bev, state) -> list:
    """Convert BEV polygon to pixel coordinates via inverse homography."""
    if state.homography_matrix is None:
        return polygon_bev

    H_inv = np.linalg.inv(state.homography_matrix)
    bev_res = state.bev_scale

    pts = np.array(polygon_bev) / bev_res  # meters → BEV pixels
    pts_h = np.hstack([pts, np.ones((len(pts), 1))])
    pixel_pts = (H_inv @ pts_h.T).T
    pixel_pts = pixel_pts[:, :2] / pixel_pts[:, 2:3]

    return pixel_pts.tolist()


def _find_overlapping_zone(structure, registry, state) -> str | None:
    """Check if a structure overlaps with any existing zone."""
    bbox = structure.get("bbox_pixel", [0, 0, 0, 0])

    # Convert normalized [0-1] coords to pixel coords if needed
    if all(0 <= v <= 1.0 for v in bbox) and state.frame_shape[0] > 1:
        H_img, W_img = state.frame_shape[:2]
        bbox = [bbox[0] * W_img, bbox[1] * H_img, bbox[2] * W_img, bbox[3] * H_img]

    struct_box = shapely_box(bbox[0], bbox[1], bbox[2], bbox[3])
    if struct_box.area < 1:
        return None

    best_zid = None
    best_overlap = 0

    for zid, zone in registry.items():
        zone_bbox = zone.get("bbox_pixel", [0, 0, 0, 0])
        zone_box = shapely_box(zone_bbox[0], zone_bbox[1], zone_bbox[2], zone_bbox[3])
        if zone_box.area < 1:
            continue
        if struct_box.intersects(zone_box):
            overlap = struct_box.intersection(zone_box).area / struct_box.area
            if overlap > best_overlap:
                best_overlap = overlap
                best_zid = zid

    if best_overlap > 0.1:
        return best_zid
    return None


def _create_zone_from_structure(zone_id, structure, state) -> dict:
    """Create a zone entry from a VLM-detected structure."""
    bbox = structure.get("bbox_pixel", [0, 0, 100, 100])
    # Use VLM's zone_implication directly — no normalization
    zone_type = structure.get("zone_implication", "unknown")

    return {
        "zone_id": zone_id,
        "business_name": _generate_zone_name(zone_type, zone_id),
        "zone_type": zone_type,
        "vlm_confidence": structure.get("confidence", 0.5),
        "description": structure.get("description", ""),
        "polygon_bev": [],
        "polygon_pixel": [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]],
        "centroid_bev": [0, 0],
        "area_m2": 0,
        "bbox_pixel": bbox,
        "depth_info": {},
        "objects": [],
        "signage": {},
        "strategy_agreement": 0,
        "contributing_strategies": ["vlm_structure"],
        "structures_detected": [structure],
    }


def _deduplicate_names(registry: dict):
    """Ensure unique business names across all zones."""
    seen = {}
    for zid, zone in registry.items():
        name = zone["business_name"]
        if name in seen:
            count = seen[name]
            seen[name] += 1
            zone["business_name"] = f"{name} ({count})"
        else:
            seen[name] = 1
