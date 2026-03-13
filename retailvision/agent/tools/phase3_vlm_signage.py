"""Phase 3 Tool t16: VLM signage reader — extract text from zone crops."""

from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM
from agent.vlm.prompts import VLM_SIGNAGE_PROMPT, format_scene_context


@ToolRegistry.register("vlm_signage_reader")
def vlm_signage_reader(state, config) -> ToolResult:
    """t16: Extract readable text, business names, and signage from zones.

    Uses the WIDE crop to capture overhead signs above zone area.
    """
    if not config.openrouter_api_key or not state.zone_crops:
        for zid in (state.fused_zones_dict or {}):
            state.zone_signage[zid] = {"text_elements": [], "primary_business_name": None}
        return ToolResult(
            success=True,
            message="VLM not available, skipping signage reader",
            data={"total_text_elements": 0},
        )

    vlm = OpenRouterVLM(
        config.openrouter_api_key,
        config.vlm_primary_model,
        config.vlm_fallback_model,
    )

    total_elements = 0
    business_names = []

    for zone_id, crops in state.zone_crops.items():
        try:
            # Use wide crop for signage (captures overhead signs)
            scene_context = format_scene_context(state.scene_layout)
            prompt = VLM_SIGNAGE_PROMPT.format(scene_context=scene_context)
            result = vlm.query_with_image(crops["wide"], prompt)
            state.zone_signage[zone_id] = result
            elements = result.get("text_elements", [])
            total_elements += len(elements)
            name = result.get("primary_business_name")
            if name:
                business_names.append(name)
        except Exception as e:
            logger.warning(f"Signage reader failed for {zone_id}: {e}")
            state.zone_signage[zone_id] = {"text_elements": [], "primary_business_name": None}

    vlm.close()

    return ToolResult(
        success=True,
        data={
            "total_text_elements": total_elements,
            "business_names_found": business_names,
        },
        message=f"Found {total_elements} text elements, "
                f"{len(business_names)} business names: {business_names}",
    )
