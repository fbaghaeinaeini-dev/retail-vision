"""Phase 3 Tool t18: VLM zone description generator."""

from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM
from agent.vlm.prompts import VLM_DESCRIBE_PROMPT, format_scene_context


@ToolRegistry.register("vlm_zone_describer")
def vlm_zone_describer(state, config) -> ToolResult:
    """t18: Generate rich text descriptions for each zone.

    Uses all collected data: objects, signage, classification, depth, behavior.
    """
    if not config.openrouter_api_key or not state.zone_crops:
        for zid in (state.fused_zones_dict or {}):
            state.zone_descriptions[zid] = f"Zone {zid}"
        return ToolResult(
            success=True,
            message="VLM not available, using default descriptions",
            data={"n_described": 0},
        )

    vlm = OpenRouterVLM(
        config.openrouter_api_key,
        config.vlm_primary_model,
        config.vlm_fallback_model,
    )

    described = 0
    for zone_id, crops in state.zone_crops.items():
        classification = state.zone_classifications.get(zone_id, {})
        signage = state.zone_signage.get(zone_id, {})
        depth = state.zone_depth_info.get(zone_id, {})
        objects = state.zone_objects.get(zone_id, [])

        business_name = (
            signage.get("primary_business_name")
            or classification.get("suggested_name")
            or f"Zone {zone_id}"
        )
        zone_type = classification.get("zone_type", "unknown")

        objects_summary = ", ".join(
            f"{o.get('name', '?')} x{o.get('count', 1)}" for o in objects[:8]
        ) or "No objects detected"

        text_elements = signage.get("text_elements", [])
        signage_summary = ", ".join(
            f"\"{t.get('text', '')}\"" for t in text_elements[:5]
        ) or "No signage found"

        scene_context = format_scene_context(state.scene_layout)
        prompt = VLM_DESCRIBE_PROMPT.format(
            scene_context=scene_context,
            business_name=business_name,
            zone_type=zone_type,
            objects_summary=objects_summary,
            signage_summary=signage_summary,
            width=depth.get("width_estimate_m", "?"),
            depth=depth.get("depth_estimate_m", "?"),
            avg_dwell="N/A",
            visits="N/A",
            peak_hour="N/A",
        )

        try:
            result = vlm.query_with_image(crops["standard"], prompt, expect_json=False)
            state.zone_descriptions[zone_id] = result
            described += 1
        except Exception as e:
            logger.warning(f"Description failed for {zone_id}: {e}")
            state.zone_descriptions[zone_id] = f"{zone_type} area"

    vlm.close()

    return ToolResult(
        success=True,
        data={"n_described": described},
        message=f"Generated descriptions for {described}/{len(state.zone_crops)} zones",
    )
