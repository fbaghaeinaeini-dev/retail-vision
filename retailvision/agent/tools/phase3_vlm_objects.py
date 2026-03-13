"""Phase 3 Tool t15: VLM object inventory per zone."""

from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM
from agent.vlm.prompts import VLM_OBJECT_INVENTORY_PROMPT, format_scene_context


@ToolRegistry.register("vlm_object_inventory")
def vlm_object_inventory(state, config) -> ToolResult:
    """t15: Ask VLM to identify every object in each zone crop.

    Uses depth context when available to help VLM gauge object sizes.
    """
    if not config.openrouter_api_key or not state.zone_crops:
        for zid in (state.fused_zones_dict or {}):
            state.zone_objects[zid] = []
        return ToolResult(
            success=True,
            message="VLM not available or no crops, skipping object inventory",
            data={"total_objects": 0},
        )

    vlm = OpenRouterVLM(
        config.openrouter_api_key,
        config.vlm_primary_model,
        config.vlm_fallback_model,
    )

    total_objects = 0
    for zone_id, crops in state.zone_crops.items():
        depth_info = state.zone_depth_info.get(zone_id, {})
        if depth_info.get("avg_depth_m"):
            depth_context = (
                f"Spatial context: This area is approximately "
                f"{depth_info['width_estimate_m']}m wide x "
                f"{depth_info['depth_estimate_m']}m deep, "
                f"at {depth_info['avg_depth_m']:.0f}m from the camera."
            )
        else:
            depth_context = ""

        scene_context = format_scene_context(state.scene_layout)
        prompt = VLM_OBJECT_INVENTORY_PROMPT.format(
            scene_context=scene_context,
            depth_context=depth_context,
        )

        try:
            result = vlm.query_with_image(crops["standard"], prompt)
            objects = result.get("objects", [])
            state.zone_objects[zone_id] = objects
            total_objects += len(objects)
        except Exception as e:
            logger.warning(f"Object inventory failed for {zone_id}: {e}")
            state.zone_objects[zone_id] = []

    vlm.close()

    return ToolResult(
        success=True,
        data={"total_object_types": total_objects},
        message=f"Found {total_objects} object types across {len(state.zone_objects)} zones",
    )
