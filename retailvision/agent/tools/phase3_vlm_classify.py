"""Phase 3 Tool t17: VLM zone classifier — fully agentic classification.

The VLM decides zone types freely based on visual evidence, scene context,
objects, signage, behavioral data, and semantic segmentation labels.
No hardcoded classification rules or zone type enums.
"""

from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM
from agent.vlm.prompts import VLM_CLASSIFY_PROMPT, format_scene_context


@ToolRegistry.register("vlm_zone_classifier")
def vlm_zone_classifier(state, config) -> ToolResult:
    """t17: Classify each zone using VLM with full scene context.

    Synthesizes: scene layout, objects, signage, SSA labels, depth, and behavior.
    VLM outputs any zone_type string — not constrained to a preset enum.
    """
    if not config.openrouter_api_key or not state.zone_crops:
        # No VLM available — mark all zones as unknown (honest, not fake)
        for zid in (state.fused_zones_dict or {}):
            state.zone_classifications[zid] = {
                "zone_type": "unknown",
                "confidence": 0.0,
                "method": "no_vlm",
            }
        return ToolResult(
            success=True,
            message=f"No VLM available — {len(state.fused_zones_dict or {})} zones set to unknown",
            data={"n_classified": 0, "method": "no_vlm"},
        )

    vlm = OpenRouterVLM(
        config.openrouter_api_key,
        config.vlm_primary_model,
        config.vlm_fallback_model,
    )

    # Build scene context once (shared across all zones)
    scene_context = format_scene_context(state.scene_layout)

    classified = 0
    for zone_id, crops in state.zone_crops.items():
        objects = state.zone_objects.get(zone_id, [])
        signage = state.zone_signage.get(zone_id, {})
        depth = state.zone_depth_info.get(zone_id, {})

        # Build context strings
        objects_list = "\n".join(
            f"- {o.get('name', '?')} x{o.get('count', 1)}" for o in objects[:15]
        ) or "None detected"

        text_elements = signage.get("text_elements", [])
        signage_list = "\n".join(
            f"- \"{t.get('text', '')}\" ({t.get('type', 'unknown')})" for t in text_elements[:10]
        ) or "None found"

        # SSA semantic labels (from segment_zone_refinement, if it ran before us)
        ssa_labels = state.zone_classifications.get(zone_id, {}).get("ssa_labels", [])
        ssa_context = ", ".join(ssa_labels) if ssa_labels else "Not available"

        # Get behavioral data from quick analytics (computed before classification)
        quick = state.quick_zone_analytics.get(zone_id, {})
        zone_area = state.fused_zones_dict.get(zone_id, {}).get("area_m2", 0)

        # Determine flow pattern from quick analytics
        flow_pattern = "unknown"
        if quick.get("avg_dwell_seconds", 0) > 30:
            flow_pattern = "lingering — people stay a while"
        elif quick.get("visits_per_hour", 0) > 50:
            flow_pattern = "high throughput — many brief visits"
        elif quick.get("total_visits", 0) < 5:
            flow_pattern = "rarely visited"
        else:
            flow_pattern = "moderate traffic"

        prompt = VLM_CLASSIFY_PROMPT.format(
            scene_layout_context=scene_context,
            ssa_context=ssa_context,
            visual_context="See image crop",
            objects_list=objects_list,
            signage_list=signage_list,
            avg_dwell=quick.get("avg_dwell_seconds", "N/A"),
            visits_per_hour=quick.get("visits_per_hour", "N/A"),
            peak_hour=quick.get("peak_hour", "N/A"),
            next_zone="N/A",  # Full flow analytics not yet available
            flow_pattern=flow_pattern,
            width=depth.get("width_estimate_m", "?"),
            depth=depth.get("depth_estimate_m", "?"),
            distance=depth.get("avg_depth_m", "?"),
            area=zone_area if zone_area else "?",
        )

        try:
            result = vlm.query_with_image(crops["standard"], prompt)
            confidence = result.get("confidence", 0)

            # Retry with wide crop if low confidence
            if confidence < config.vlm_confidence_threshold:
                logger.info(f"  Low confidence ({confidence:.2f}) for {zone_id}, retrying with wide crop")
                result = vlm.query_with_image(crops["wide"], prompt)
                confidence = result.get("confidence", 0)

            # Preserve any existing SSA labels
            if ssa_labels:
                result["ssa_labels"] = ssa_labels

            state.zone_classifications[zone_id] = result
            if confidence >= config.vlm_confidence_threshold:
                classified += 1
        except Exception as e:
            logger.warning(f"Zone classification failed for {zone_id}: {e}")
            state.zone_classifications[zone_id] = {
                "zone_type": "unknown",
                "confidence": 0.0,
            }

    vlm.close()

    return ToolResult(
        success=True,
        data={"n_classified": classified, "n_total": len(state.zone_crops)},
        message=f"Classified {classified}/{len(state.zone_crops)} zones with confidence >= {config.vlm_confidence_threshold}",
    )
