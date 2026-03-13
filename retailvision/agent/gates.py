"""Decision gates for the hybrid ReAct orchestrator.

Three gates provide LLM reasoning between pipeline phases:
- Gate 1 (Strategy): After Phase 1, decides strategy profile and all parameters
- Gate 2 (Zone Review): After Phase 2, reviews discovered zones
- Gate 3 (Classification Review): After Phase 3, reviews zone classifications
"""

from __future__ import annotations

import json

import httpx
from loguru import logger

from agent.config import PipelineConfig
from agent.state import AgentState
from agent.strategy_profiles import get_profile, get_profile_descriptions, get_profile_names
from agent.vlm.openrouter_client import OpenRouterVLM, encode_frame_to_b64
from agent.vlm.prompts import (
    GATE1_STRATEGY_PROMPT,
    GATE2_ZONE_REVIEW_PROMPT,
    GATE3_CLASSIFICATION_REVIEW_PROMPT,
)

# Clamping ranges for all LLM-tunable parameters
_PARAM_RANGES: dict[str, tuple[float, float]] = {
    "dwell_speed_threshold_m_s": (0.1, 2.0),
    "min_dwell_seconds": (3.0, 120.0),
    "confinement_radius_m": (0.5, 10.0),
    "stdbscan_spatial_eps_m": (0.5, 8.0),
    "stdbscan_temporal_eps_s": (10.0, 300.0),
    "stdbscan_min_samples": (2, 20),
    "occupancy_grid_cell_m": (0.2, 2.0),
    "traj_edge_weight_threshold": (1, 10),
    "traj_resolution": (0.1, 1.0),
    "min_zone_area_m2": (0.5, 50.0),
    "merge_threshold_m2": (1.0, 20.0),
    "merge_max_distance_m": (1.0, 15.0),
    "max_zone_area_m2": (20.0, 500.0),
    "fusion_min_strategies": (1, 3),
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _call_llm_text(prompt: str, config: PipelineConfig) -> dict:
    """Call LLM (text-only, no image) and parse JSON response."""
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
            timeout=60,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError("No JSON in LLM response")
    except Exception as e:
        logger.warning(f"Gate LLM call failed: {e}")
        return {}


def _call_vlm_with_image(image_b64: str, prompt: str, config: PipelineConfig) -> dict:
    """Call VLM with image and parse JSON response."""
    try:
        vlm = OpenRouterVLM(
            config.openrouter_api_key,
            config.vlm_primary_model,
            config.vlm_fallback_model,
        )
        result = vlm.query_with_image(image_b64, prompt)
        vlm.close()
        return result if isinstance(result, dict) else {}
    except Exception as e:
        logger.warning(f"Gate VLM call failed: {e}")
        return {}


def run_gate1_strategy(state: AgentState, config: PipelineConfig) -> dict:
    """Gate 1: LLM decides strategy profile and all parameters.

    Called after Phase 1 (scene understanding) completes.
    Returns: {strategy_profile, parameters, skip_tools, reasoning}
    """
    if not config.openrouter_api_key:
        logger.info("Gate 1: No API key — using 'general' profile with defaults")
        return {"strategy_profile": "general", "parameters": {}, "skip_tools": []}

    stats = state.adaptive_params
    prompt = GATE1_STRATEGY_PROMPT.format(
        scene_layout_json=json.dumps(state.scene_layout, indent=2, default=str),
        n_tracks=stats.get("n_tracks", 0),
        duration_minutes=stats.get("duration_minutes", 0),
        median_speed=stats.get("median_speed_m_s", 0),
        density=stats.get("density_tracks_per_min", 0),
        x_range=stats.get("x_range_m", 0),
        y_range=stats.get("y_range_m", 0),
        depth_status="available" if state.scene_depth_map is not None else "not available",
        profile_descriptions=get_profile_descriptions(),
    )

    decision = _call_llm_text(prompt, config)
    if not decision:
        return {"strategy_profile": "general", "parameters": {}, "skip_tools": []}

    # Validate profile name
    profile_name = decision.get("strategy_profile", "general")
    if profile_name not in get_profile_names():
        logger.warning(f"Gate 1: Unknown profile '{profile_name}', falling back to 'general'")
        profile_name = "general"

    # Clamp all parameters to safe ranges
    raw_params = decision.get("parameters", {})
    clamped = {}
    for key, value in raw_params.items():
        if key in _PARAM_RANGES:
            lo, hi = _PARAM_RANGES[key]
            clamped[key] = _clamp(float(value), lo, hi)

    logger.info(f"Gate 1: profile={profile_name}, params={clamped}")
    logger.info(f"Gate 1 reasoning: {decision.get('reasoning', 'N/A')}")

    return {
        "strategy_profile": profile_name,
        "parameters": clamped,
        "skip_tools": decision.get("skip_tools", []),
        "reasoning": decision.get("reasoning", ""),
    }


def apply_gate1_decision(
    decision: dict, state: AgentState, config: PipelineConfig
) -> None:
    """Apply Gate 1 decision to state and config."""
    # Apply strategy profile
    profile_name = decision.get("strategy_profile", "general")
    profile = get_profile(profile_name)
    state.strategy_profile = profile_name
    state.active_phase2_tools = list(profile["phase2_tools"])
    state.active_phase3_tools = list(profile["phase3_tools"])

    # Remove skipped tools
    skip = set(decision.get("skip_tools", []))
    state.active_phase3_tools = [t for t in state.active_phase3_tools if t not in skip]

    # Apply LLM-chosen parameters to config (clamped)
    params = decision.get("parameters", {})
    for key, value in params.items():
        if hasattr(config, key):
            if key in _PARAM_RANGES:
                lo, hi = _PARAM_RANGES[key]
                value = _clamp(float(value), lo, hi)
            setattr(config, key, type(getattr(config, key))(value))

    # Store decision for dashboard
    state.llm_chosen_params = {
        "strategy_profile": profile_name,
        "applied": params,
        "reasoning": decision.get("reasoning", ""),
        "skip_tools": list(skip),
    }
    state.tool_plan = {
        "phase2": state.active_phase2_tools,
        "phase3": state.active_phase3_tools,
        "skip": list(skip),
    }


def run_gate2_zone_review(state: AgentState, config: PipelineConfig) -> dict:
    """Gate 2: LLM reviews discovered zones.

    Called after Phase 2 (zone discovery) completes.
    Returns: {accept, issues, rerun_with_adjustments, reasoning}
    """
    if not config.openrouter_api_key or state.reference_frame is None:
        return {"accept": True, "issues": [], "reasoning": "No VLM — auto-accept"}

    # Build zone summary
    zones = state.fused_zones_dict or {}
    zone_lines = []
    for zid, z in zones.items():
        zone_lines.append(
            f"  {zid}: area={z.get('area_m2', 0):.1f}m2, "
            f"strategies={z.get('strategy_agreement', 0)}, "
            f"contributors={z.get('contributing_strategies', [])}"
        )
    zone_summary = "\n".join(zone_lines) or "No zones discovered"

    prompt = GATE2_ZONE_REVIEW_PROMPT.format(
        venue_type=state.scene_layout.get("venue_type", "unknown"),
        strategy_profile=getattr(state, "strategy_profile", "general"),
        n_zones=len(zones),
        zone_summary=zone_summary,
    )

    image_b64 = encode_frame_to_b64(state.reference_frame)
    decision = _call_vlm_with_image(image_b64, prompt, config)
    if not decision:
        return {"accept": True, "issues": [], "reasoning": "VLM call failed — auto-accept"}

    logger.info(f"Gate 2: accept={decision.get('accept', True)}, "
                f"issues={decision.get('issues', [])}")

    return decision


def apply_gate2_decision(
    decision: dict, state: AgentState, config: PipelineConfig
) -> bool:
    """Apply Gate 2 decision. Returns True if Phase 2 should re-run."""
    if decision.get("accept", True):
        return False

    adjustments = decision.get("rerun_with_adjustments")
    if not adjustments or state.phase2_retry_count >= config.max_phase2_retries:
        logger.info("Gate 2: Not accepted but no re-run (max retries or no adjustments)")
        return False

    # Apply adjusted parameters
    for key, value in adjustments.items():
        if key in _PARAM_RANGES and hasattr(config, key):
            lo, hi = _PARAM_RANGES[key]
            setattr(config, key, type(getattr(config, key))(_clamp(float(value), lo, hi)))

    state.phase2_retry_count += 1
    logger.info(f"Gate 2: Re-running Phase 2 (retry {state.phase2_retry_count})")
    return True


def run_gate3_classification_review(state: AgentState, config: PipelineConfig) -> dict:
    """Gate 3: LLM reviews zone classifications for contradictions.

    Called after Phase 3 enrichment completes.
    Returns: {accept, reclassify, reasoning}
    """
    if not config.openrouter_api_key:
        return {"accept": True, "reclassify": [], "reasoning": "No VLM — auto-accept"}

    # Build classification summary
    registry = state.zone_registry or {}
    lines = []
    for zid, z in registry.items():
        lines.append(
            f"  {zid}: type={z.get('zone_type', '?')}, "
            f"confidence={z.get('vlm_confidence', 0):.2f}, "
            f"name={z.get('business_name', 'unnamed')}"
        )
    classification_summary = "\n".join(lines) or "No classifications"

    prompt = GATE3_CLASSIFICATION_REVIEW_PROMPT.format(
        venue_type=state.scene_layout.get("venue_type", "unknown"),
        classification_summary=classification_summary,
    )

    decision = _call_llm_text(prompt, config)
    if not decision:
        return {"accept": True, "reclassify": [], "reasoning": "LLM call failed — auto-accept"}

    logger.info(f"Gate 3: accept={decision.get('accept', True)}, "
                f"reclassify={len(decision.get('reclassify', []))} zones")

    return decision


def apply_gate3_decision(decision: dict, state: AgentState) -> None:
    """Apply Gate 3 reclassifications to zone registry."""
    reclassifications = decision.get("reclassify", [])
    for entry in reclassifications:
        zid = entry.get("zone_id")
        new_type = entry.get("new_type")
        if zid in state.zone_registry and new_type:
            old_type = state.zone_registry[zid].get("zone_type", "unknown")
            state.zone_registry[zid]["zone_type"] = new_type
            state.zone_registry[zid]["reclassified_from"] = old_type
            state.zone_registry[zid]["reclassification_reason"] = entry.get("reason", "")
            logger.info(f"Gate 3: Reclassified {zid}: {old_type} -> {new_type}")
