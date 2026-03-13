"""Phase 3 Tool t14: Depth analysis on zone crops.

Uses the scene depth map (from t06) to estimate physical dimensions
for each zone. Falls back to BEV polygon area if no depth available.
"""

import numpy as np
from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


@ToolRegistry.register("depth_zone_analysis")
def depth_zone_analysis(state, config) -> ToolResult:
    """t14: Estimate zone physical dimensions from depth data.

    If depth map available: extract depth within zone bbox, compute
    physical width/height using pinhole model.
    If not: estimate from BEV polygon area.
    """
    zones = state.fused_zones_dict or state.zone_registry_draft

    if state.scene_depth_map is None:
        # No depth — estimate from BEV polygon area
        for zone_id, zone in zones.items():
            area_m2 = zone.get("area_m2", 4.0)
            side = area_m2 ** 0.5
            state.zone_depth_info[zone_id] = {
                "avg_depth_m": None,
                "depth_range_m": 0,
                "width_estimate_m": round(side, 1),
                "depth_estimate_m": round(side, 1),
                "source": "bev_polygon",
            }
        return ToolResult(
            success=True,
            data={"method": "bev_polygon"},
            message=f"Estimated sizes from BEV polygon for {len(zones)} zones (no depth)",
        )

    depth_map = state.scene_depth_map
    focal = state.scene_depth_stats.get("focal_length_from_depth") or (state.frame_shape[1] * 1.15)

    zones_with_depth = 0

    for zone_id, zone in zones.items():
        bbox = zone.get("bbox_pixel", [0, 0, 100, 100])
        x1, y1, x2, y2 = [int(v) for v in bbox]

        # Clamp to depth map bounds
        dh, dw = depth_map.shape[:2]
        x1 = max(0, min(x1, dw - 1))
        y1 = max(0, min(y1, dh - 1))
        x2 = max(0, min(x2, dw))
        y2 = max(0, min(y2, dh))

        zone_depth = depth_map[y1:y2, x1:x2]
        valid = zone_depth[zone_depth > 0.1]

        if len(valid) > 10:
            avg_depth = float(np.median(valid))
            depth_range = float(valid.max() - valid.min())
            width_m = (x2 - x1) * avg_depth / focal
            height_m = (y2 - y1) * avg_depth / focal
            zones_with_depth += 1
            source = "depth_pro"
        else:
            avg_depth = None
            depth_range = 0
            area = zone.get("area_m2", 4.0)
            width_m = area ** 0.5
            height_m = width_m
            source = "bev_polygon"

        state.zone_depth_info[zone_id] = {
            "avg_depth_m": avg_depth,
            "depth_range_m": depth_range,
            "width_estimate_m": round(width_m, 1),
            "depth_estimate_m": round(height_m, 1),
            "source": source,
        }

    return ToolResult(
        success=True,
        data={"zones_with_depth": zones_with_depth, "total_zones": len(zones)},
        message=f"Depth analysis: {zones_with_depth}/{len(zones)} zones with depth data",
    )
