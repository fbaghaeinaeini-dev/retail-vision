"""Strategy profiles for scene-adaptive zone discovery.

The LLM selects a profile based on scene analysis. Each profile defines
which Phase 2 and Phase 3 tools to run, optimized for the scene type.
"""

from __future__ import annotations

STRATEGY_PROFILES: dict[str, dict] = {
    "general": {
        "description": "Default profile — all strategies, full enrichment",
        "phase2_tools": [
            "compute_dwell_points",
            "strategy_dwell_clustering",
            "strategy_occupancy_grid",
            "strategy_trajectory_graph",
            "fuse_zone_candidates",
            "vlm_detect_structures",
        ],
        "phase3_tools": [
            "crop_zone_images",
            "depth_zone_analysis",
            "segment_zone_refinement",
            "vlm_object_inventory",
            "vlm_signage_reader",
            "vlm_zone_classifier",
            "vlm_zone_describer",
            "merge_zone_registry",
        ],
    },
    "pedestrian_indoor": {
        "description": "Indoor spaces with walking people (malls, offices, hospitals)",
        "phase2_tools": [
            "compute_dwell_points",
            "strategy_dwell_clustering",
            "strategy_occupancy_grid",
            "strategy_trajectory_graph",
            "fuse_zone_candidates",
            "vlm_detect_structures",
        ],
        "phase3_tools": [
            "crop_zone_images",
            "depth_zone_analysis",
            "segment_zone_refinement",
            "vlm_object_inventory",
            "vlm_signage_reader",
            "vlm_zone_classifier",
            "vlm_zone_describer",
            "merge_zone_registry",
        ],
    },
    "pedestrian_outdoor": {
        "description": "Outdoor spaces — markets, plazas, campuses, parks",
        "phase2_tools": [
            "compute_dwell_points",
            "strategy_occupancy_grid",
            "strategy_trajectory_graph",
            "fuse_zone_candidates",
            "vlm_detect_structures",
        ],
        "phase3_tools": [
            "crop_zone_images",
            "vlm_object_inventory",
            "vlm_signage_reader",
            "vlm_zone_classifier",
            "vlm_zone_describer",
            "merge_zone_registry",
        ],
    },
    "high_traffic": {
        "description": "Corridors, stations, intersections — flow matters more than dwell",
        "phase2_tools": [
            "compute_dwell_points",
            "strategy_occupancy_grid",
            "strategy_trajectory_graph",
            "fuse_zone_candidates",
        ],
        "phase3_tools": [
            "crop_zone_images",
            "vlm_object_inventory",
            "vlm_zone_classifier",
            "vlm_zone_describer",
            "merge_zone_registry",
        ],
    },
    "sparse_activity": {
        "description": "Low activity — warehouses, parking, restricted areas",
        "phase2_tools": [
            "compute_dwell_points",
            "strategy_dwell_clustering",
            "strategy_occupancy_grid",
            "fuse_zone_candidates",
            "vlm_detect_structures",
        ],
        "phase3_tools": [
            "crop_zone_images",
            "segment_zone_refinement",
            "vlm_object_inventory",
            "vlm_zone_classifier",
            "merge_zone_registry",
        ],
    },
    "monitored_perimeter": {
        "description": "Perimeter/gate monitoring — entrances, fences, checkpoints",
        "phase2_tools": [
            "compute_dwell_points",
            "strategy_occupancy_grid",
            "fuse_zone_candidates",
            "vlm_detect_structures",
        ],
        "phase3_tools": [
            "crop_zone_images",
            "vlm_object_inventory",
            "vlm_zone_classifier",
            "merge_zone_registry",
        ],
    },
}


def get_profile(name: str) -> dict:
    """Return a strategy profile by name, falling back to 'general'."""
    return STRATEGY_PROFILES.get(name, STRATEGY_PROFILES["general"])


def get_profile_names() -> list[str]:
    """Return list of available profile names."""
    return list(STRATEGY_PROFILES.keys())


def get_profile_descriptions() -> str:
    """Format all profiles as text for LLM prompt injection."""
    lines = []
    for name, profile in STRATEGY_PROFILES.items():
        tools = ", ".join(profile["phase2_tools"])
        lines.append(f"- {name}: {profile['description']} (tools: {tools})")
    return "\n".join(lines)
