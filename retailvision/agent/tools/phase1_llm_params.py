"""Phase 1 Tool: LLM decides Phase 2 zone discovery parameters.

Instead of hardcoded scene profiles, the LLM reasons about what
parameters make sense given the scene layout, tracking stats, and
venue type it identified.
"""

import json

import httpx
from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.prompts import VLM_PHASE2_PARAMS_PROMPT


# Sane ranges — clamp LLM output to prevent extreme values
_PARAM_RANGES = {
    "dwell_threshold_seconds": (3.0, 60.0),
    "dwell_speed_threshold_m_s": (0.1, 2.0),
    "cluster_radius_meters": (0.5, 8.0),
    "min_zone_area_m2": (0.5, 20.0),
    "occupancy_grid_cell_m": (0.2, 2.0),
    "merge_small_zone_m2": (1.0, 10.0),
    "max_zone_area_m2": (20.0, 200.0),
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@ToolRegistry.register("llm_set_phase2_params")
def llm_set_phase2_params(state, config) -> ToolResult:
    """LLM decides zone discovery parameters based on scene analysis.

    Uses the scene layout (from VLM) and tracking statistics to choose
    appropriate thresholds for dwell detection, clustering, and zone sizing.
    Falls back to config defaults if LLM is unavailable.
    """
    if not config.openrouter_api_key:
        return ToolResult(
            success=True,
            message="No API key — using default parameters",
            data={"method": "defaults"},
        )

    # Build context from Phase 1 outputs
    scene_desc = json.dumps(state.scene_layout, indent=2, default=str)
    stats = state.adaptive_params

    prompt = VLM_PHASE2_PARAMS_PROMPT.format(
        scene_layout_json=scene_desc,
        n_tracks=stats.get("n_tracks", 0),
        duration_minutes=stats.get("duration_minutes", 0),
        median_speed=stats.get("median_speed_m_s", 0),
        density=stats.get("density_tracks_per_min", 0),
    )

    try:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.vlm_primary_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]

        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            params = json.loads(text[start:end])
        else:
            raise ValueError("No JSON found in LLM response")

    except Exception as e:
        logger.warning(f"LLM param selection failed: {e}, using defaults")
        return ToolResult(
            success=True,
            message=f"LLM params failed ({e}), using defaults",
            data={"method": "defaults"},
        )

    # Apply LLM-chosen params to config (clamped to safe ranges)
    applied = {}

    if "dwell_threshold_seconds" in params:
        lo, hi = _PARAM_RANGES["dwell_threshold_seconds"]
        config.min_dwell_seconds = _clamp(float(params["dwell_threshold_seconds"]), lo, hi)
        applied["min_dwell_seconds"] = config.min_dwell_seconds

    if "dwell_speed_threshold_m_s" in params:
        lo, hi = _PARAM_RANGES["dwell_speed_threshold_m_s"]
        config.dwell_speed_threshold_m_s = _clamp(float(params["dwell_speed_threshold_m_s"]), lo, hi)
        applied["dwell_speed_threshold_m_s"] = config.dwell_speed_threshold_m_s

    if "cluster_radius_meters" in params:
        lo, hi = _PARAM_RANGES["cluster_radius_meters"]
        config.stdbscan_spatial_eps_m = _clamp(float(params["cluster_radius_meters"]), lo, hi)
        applied["stdbscan_spatial_eps_m"] = config.stdbscan_spatial_eps_m

    if "min_zone_area_m2" in params:
        lo, hi = _PARAM_RANGES["min_zone_area_m2"]
        config.min_zone_area_m2 = _clamp(float(params["min_zone_area_m2"]), lo, hi)
        applied["min_zone_area_m2"] = config.min_zone_area_m2

    if "occupancy_grid_cell_m" in params:
        lo, hi = _PARAM_RANGES["occupancy_grid_cell_m"]
        config.occupancy_grid_cell_m = _clamp(float(params["occupancy_grid_cell_m"]), lo, hi)
        applied["occupancy_grid_cell_m"] = config.occupancy_grid_cell_m

    state.llm_chosen_params = {
        "raw_llm_response": params,
        "applied": applied,
        "reasoning": params.get("reasoning", ""),
    }

    logger.info(f"LLM chose params: {applied}")

    return ToolResult(
        success=True,
        data={"method": "llm", "params": applied},
        message=f"LLM set {len(applied)} parameters: {applied}",
    )
