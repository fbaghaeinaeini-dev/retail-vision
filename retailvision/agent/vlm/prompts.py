"""All VLM prompt templates for the pipeline.

Centralized prompt management for all VLM tools.
Prompts are domain-agnostic — the VLM decides what kind of scene this is,
what zone types exist, and what objects matter. No hardcoded restaurant/mall vocabulary.
"""

# ── Shared helper ──

def format_scene_context(scene_layout: dict, zone_id: str = None) -> str:
    """Format scene_layout dict into text suitable for prompt injection."""
    if not scene_layout:
        return "No scene context available."

    parts = [f"Venue type: {scene_layout.get('venue_type', 'unknown')}"]

    layout_desc = scene_layout.get("layout_description", "")
    if layout_desc:
        parts.append(f"Layout: {layout_desc}")

    areas = scene_layout.get("areas", [])
    if areas:
        area_strs = [
            f"  - {a.get('description', '?')} ({a.get('location', '?')}, type: {a.get('estimated_type', '?')})"
            for a in areas[:8]
        ]
        parts.append("Areas identified:\n" + "\n".join(area_strs))

    corridor = scene_layout.get("main_corridor_direction", "")
    if corridor:
        parts.append(f"Main corridor: {corridor}")

    return "\n".join(parts)


# ── Phase 1 ──

VLM_SCENE_LAYOUT_PROMPT = """Analyze this CCTV camera image and describe the spatial layout of the scene.

Identify:
1. What type of venue/space is this? (be specific — e.g. "indoor food court", "warehouse floor",
   "hospital waiting area", "parking garage", "retail shopping mall", "outdoor market", etc.)
2. Where are the distinct functional areas? (top, bottom, left, right, center)
3. Where are the main walkways/corridors?
4. Where are areas where people stop/gather/work?
5. Where are entrances/exits?

Respond ONLY in JSON:
{{
    "venue_type": "<specific description of the venue>",
    "layout_description": "<2-3 sentence description of spatial arrangement>",
    "areas": [
        {{
            "description": "<what is here>",
            "location": "<top-left | top-center | top-right | center-left | center | center-right | bottom-left | bottom-center | bottom-right>",
            "estimated_type": "<your best description of what kind of area this is>"
        }}
    ],
    "main_corridor_direction": "horizontal | vertical | diagonal | complex",
    "estimated_capacity": "<low (<20) | medium (20-100) | high (>100)>"
}}
"""

# ── Phase 1: LLM-decided parameters ──

VLM_PHASE2_PARAMS_PROMPT = """You are configuring a person-tracking zone discovery system.

SCENE ANALYSIS (from VLM):
{scene_layout_json}

TRACKING STATISTICS:
- Total tracks: {n_tracks}
- Duration: {duration_minutes} minutes
- Median walking speed: {median_speed} m/s
- Track density: {density} tracks/minute

Based on this scene, choose parameters for zone discovery. Think about:
- How long do people typically stop in this type of venue? (dwell threshold)
- How close should dwell points be to form a zone? (cluster radius)
- What's the smallest meaningful zone in this space? (min area)
- What grid resolution captures the activity patterns? (grid cell size)

Respond ONLY in JSON:
{{
    "dwell_threshold_seconds": <5-60, how long someone must stop to count as dwelling>,
    "dwell_speed_threshold_m_s": <0.1-2.0, speed below which someone is "stopped">,
    "cluster_radius_meters": <0.5-8.0, max distance between dwell points in same zone>,
    "min_zone_area_m2": <0.5-20.0, smallest zone to keep>,
    "occupancy_grid_cell_m": <0.2-2.0, spatial grid resolution>,
    "reasoning": "<2-3 sentences explaining your choices for this scene>"
}}
"""

# ── Phase 2 ──

VLM_STRUCTURES_PROMPT = """Analyze this CCTV image and identify all FIXED STRUCTURAL ELEMENTS that
define functional areas. For each element, provide its approximate
location as a bounding box in normalized coordinates [0-1].

Look for ANY permanent structures that define zones:
- Counters, desks, service points, reception areas
- Furniture clusters (tables, chairs, workstations, benches)
- Doorways, entrances, exits, gates, turnstiles
- Barriers, railings, pillars, walls, partitions
- Kiosks, vending machines, ATMs, display stands
- Signage, menu boards, information displays
- Shelving, display cases, storage racks
- Any fixed infrastructure that creates boundaries

For each structure found:
- type: what it is (be descriptive)
- bbox: [x_min, y_min, x_max, y_max] in normalized 0-1 coordinates
- zone_implication: what kind of functional area this structure suggests
- confidence: how certain you are [0-1]

Respond ONLY in JSON:
{{
    "structures": [
        {{
            "type": "<descriptive name>",
            "bbox": [0.2, 0.15, 0.35, 0.35],
            "zone_implication": "<what kind of area this creates>",
            "confidence": 0.9,
            "description": "<brief description>"
        }}
    ]
}}
"""

# ── Phase 3 ──

VLM_OBJECT_INVENTORY_PROMPT = """You are analyzing a cropped region from a CCTV camera.

SCENE CONTEXT:
{scene_context}

{depth_context}

List EVERY distinct object you can identify in this image.
Be specific and thorough — describe what you actually see, not what you expect to see.

For each object provide:
- name: specific name (e.g. "round wooden table", "metal shelving unit", "reception desk")
- count: how many visible
- location: where in the crop ("left", "center", "right", "background")
- condition/state: relevant details ("occupied", "empty", "lit up", "in use")

Respond ONLY in JSON:
{{
    "objects": [
        {{
            "name": "<specific object name>",
            "count": 4,
            "location": "center",
            "state": "<current state>"
        }}
    ],
    "total_object_types": 0,
    "scene_density": "sparse | moderate | dense"
}}
"""

VLM_SIGNAGE_PROMPT = """Examine this image VERY carefully for ANY readable text, signage, logos, or branding.

SCENE CONTEXT:
{scene_context}

Your PRIMARY goal is to identify the NAME of whatever business or area this zone represents.
Look especially at:
- Illuminated signs above storefronts or counters (often the largest text)
- Brand logos (even partial or at an angle)
- Text on awnings, fascia boards, or lightboxes
- Boards or displays with text
- Text on uniforms, packaging, or equipment
- Department/area names, room numbers, directional signs

Also look for:
- Price lists, menus, information boards
- Directional signs (Exit, Entrance, Restrooms, etc.)
- Digital displays, screens, monitors with text
- Any text in ANY language — transcribe in original script AND provide English translation

For each text element found:
- text: the exact text as written (preserve capitalization and original script)
- translation: English translation if text is in another language, else null
- type: "business_name" | "area_name" | "directional" | "info" | "brand_logo" | "price" | "other"
- confidence: how confident you are in the reading [0-1]
- location: where in the image

Respond ONLY in JSON:
{{
    "text_elements": [
        {{
            "text": "<exact text>",
            "translation": null,
            "type": "business_name",
            "confidence": 0.95,
            "location": "<where in image>"
        }}
    ],
    "primary_business_name": "<main name if found, else null>",
    "category_hint": "<what kind of business/area this seems to be, based on signage>"
}}
"""

VLM_CLASSIFY_PROMPT = """Classify this zone from a CCTV camera.

SCENE CONTEXT (from full-frame analysis):
{scene_layout_context}

SEMANTIC SEGMENTATION LABELS IN THIS ZONE:
{ssa_context}

VISUAL EVIDENCE (from this image crop):
{visual_context}

OBJECTS DETECTED IN THIS ZONE:
{objects_list}

SIGNAGE FOUND:
{signage_list}

BEHAVIORAL DATA (from person tracking):
- Average dwell time: {avg_dwell}s
- Visitors per hour: {visits_per_hour}
- Peak hour: {peak_hour}:00
- Most common next destination: {next_zone}
- Flow pattern: {flow_pattern}

SPATIAL DATA:
- Estimated size: {width}m x {depth}m
- Distance from camera: {distance}m
- Area: {area}m2

Based on ALL this evidence, classify this zone. Use your own judgment — do NOT
limit yourself to predefined categories. Common zone types include corridor,
seating_area, entrance, exit, shop, service_counter, etc., but you can use
ANY descriptive type that fits (e.g. loading_dock, prayer_room, parking_space,
nurse_station, checkout_lane, etc.).

If signage reveals a specific business or area name, ALWAYS use it as suggested_name.

Respond ONLY in JSON:
{{
    "zone_type": "<your best classification — any descriptive snake_case string>",
    "confidence": 0.0,
    "reasoning": "2-3 sentences explaining why this classification",
    "alternative_type": null,
    "alternative_confidence": null,
    "suggested_name": "<business name from signage if visible, else a descriptive name>"
}}
"""

VLM_DESCRIBE_PROMPT = """Write a 3-5 sentence description of this zone for an analytics report.

SCENE CONTEXT:
{scene_context}

Zone: "{business_name}" (classified as: {zone_type})
Objects: {objects_summary}
Signage: {signage_summary}
Size: approximately {width}m x {depth}m
Behavioral: {avg_dwell}s avg dwell, {visits}/hr, peak at {peak_hour}:00

Write a professional but concise description that:
1. States what the zone IS (type, business/function)
2. Describes its physical characteristics (size, key objects)
3. Summarizes its usage patterns (busy times, dwell behavior)
4. Notes anything distinctive

Respond with ONLY the description text, no JSON.
"""

# ── Phase 1/6: Tool Planning ──

VLM_TOOL_PLANNER_PROMPT = """You are planning a zone discovery pipeline for a CCTV analytics system.

SCENE ANALYSIS:
{scene_layout_json}

TRACKING STATS:
{track_stats}

AVAILABLE TOOLS (Phase 2 - Zone Discovery):
{phase2_tools}

AVAILABLE TOOLS (Phase 3 - Zone Enrichment):
{phase3_tools}

Decide which tools to run and in what order.
- Phase 2 tools discover zones from movement data and visual structures.
- Phase 3 tools enrich zones with detailed analysis.

Rules:
- compute_dwell_points must always run (provides input to strategies).
- fuse_zone_candidates must always run after strategies (merges them).
- crop_zone_images must run before any VLM zone analysis.
- merge_zone_registry must be last in Phase 3.
- You can skip tools that aren't useful for this scene.

Respond ONLY in JSON:
{{
    "phase2_tools": ["compute_dwell_points", ...],
    "phase3_tools": ["crop_zone_images", ...],
    "reasoning": "<why these tools for this scene>"
}}
"""

# ── Phase 5: Validation ──

VLM_VALIDATION_PROMPT = """You are validating a zone discovery result from a CCTV analytics system.

SCENE: {scene_description}
ZONES FOUND: {n_zones}
Zone summary:
{zone_summary}

QUANTITATIVE METRICS:
- Silhouette score: {silhouette} (cluster separation, -1 to 1, higher=better)
- Coverage: {coverage_pct}% of dwell points fall within zones
- VLM classification confidence: {vlm_avg}
- Multi-strategy agreement: {multi_strat_pct}%

The attached image shows all discovered zones overlaid on the camera view.

Evaluate whether this is a reasonable zone discovery result:
- Are the zone boundaries sensible for this type of venue?
- Are there obvious missed areas where people gather?
- Are there redundant or overlapping zones that should be merged?
- Is the number of zones reasonable for this scene?
- Do the zone names and types make sense?

Respond ONLY in JSON:
{{
    "passed": true,
    "overall_score": 0.8,
    "issues": ["<any problems found>"],
    "suggestions": ["<improvements if any>"]
}}
"""

# ── Phase 6 ──

VLM_VIZ_PLANNER_PROMPT = """You are a data visualization expert planning a dashboard for analytics.

SCENE: {scene_type}
ZONES: {n_zones} ({zone_types_summary})
DATA: {n_tracks} visitors, {duration}, depth {depth_status}
HIGHLIGHTS: {key_findings}

Available visualization types:
1. zone_map_perspective — zones overlaid on camera image
2. zone_map_bev — bird's eye view zone map
3. heatmap_perspective — density heatmap on camera view
4. heatmap_bev — density heatmap on BEV
5. sankey_flow — zone-to-zone transition diagram (skip if < 3 zones)
6. temporal_heatmap — zone x hour occupancy matrix
7. bar_chart — zone metric comparison
8. pie_chart — demographic distributions
9. line_chart — time series
10. 3d_pointcloud — Three.js depth scene (skip if no depth data)
11. trajectory_replay — animated track playback
12. zone_detail_cards — individual zone summaries
13. flow_arrows_map — directional arrows showing major flows on map

Select the optimal set. NOT everything — only what tells the story.
Order by importance. Include at most 8 visualizations.

Respond ONLY in JSON:
{{
    "visualizations": [
        {{"type": "zone_map_perspective", "priority": 1, "reason": "..."}}
    ],
    "highlighted_zones": [],
    "kpi_metrics": ["total_visitors", "avg_dwell"],
    "theme": "cool"
}}
"""

# ── Decision Gate Prompts ──

GATE1_STRATEGY_PROMPT = """You are configuring a CCTV analytics system for zone discovery.

SCENE ANALYSIS (from camera image):
{scene_layout_json}

TRACKING STATISTICS:
- Total tracks: {n_tracks}
- Duration: {duration_minutes} minutes
- Median walking speed: {median_speed} m/s
- Track density: {density} tracks/minute
- Spatial spread: {x_range}m x {y_range}m

DEPTH DATA: {depth_status}

AVAILABLE STRATEGY PROFILES:
{profile_descriptions}

Based on this scene, choose:

1. **strategy_profile**: Which profile best fits this scene?
2. **parameters**: Tune ALL zone discovery parameters for this scene:
   - dwell_speed_threshold_m_s (0.1-2.0): speed below which someone is "stopped"
   - min_dwell_seconds (3-120): minimum stop duration to count as dwelling
   - confinement_radius_m (0.5-10.0): max radius of dwelling movement
   - stdbscan_spatial_eps_m (0.5-8.0): cluster radius for dwell points
   - stdbscan_temporal_eps_s (10-300): temporal window for clustering
   - stdbscan_min_samples (2-20): minimum points per cluster
   - occupancy_grid_cell_m (0.2-2.0): spatial grid resolution
   - traj_edge_weight_threshold (1-10): minimum edge weight for trajectory graph
   - traj_resolution (0.1-1.0): trajectory discretization resolution
   - min_zone_area_m2 (0.5-50.0): smallest zone to keep
   - merge_threshold_m2 (1.0-20.0): zones smaller than this get merged
   - merge_max_distance_m (1.0-15.0): max centroid distance for merging
   - max_zone_area_m2 (20-500): trigger watershed splitting above this
   - fusion_min_strategies (1-3): minimum strategies that must agree
3. **skip_tools**: Any Phase 3 tools to skip (e.g. skip signage reader for a warehouse)

Think step by step about what makes sense for THIS specific scene.

Respond ONLY in JSON:
{{
    "strategy_profile": "<profile name>",
    "parameters": {{
        "dwell_speed_threshold_m_s": 0.5,
        "min_dwell_seconds": 10.0,
        "confinement_radius_m": 2.0,
        "stdbscan_spatial_eps_m": 2.0,
        "stdbscan_temporal_eps_s": 60.0,
        "stdbscan_min_samples": 5,
        "occupancy_grid_cell_m": 0.5,
        "traj_edge_weight_threshold": 3,
        "traj_resolution": 0.3,
        "min_zone_area_m2": 1.0,
        "merge_threshold_m2": 2.5,
        "merge_max_distance_m": 4.0,
        "max_zone_area_m2": 50.0,
        "fusion_min_strategies": 2
    }},
    "skip_tools": [],
    "reasoning": "<2-3 sentences explaining your choices>"
}}
"""

GATE2_ZONE_REVIEW_PROMPT = """Review the zone discovery results from a CCTV scene.

SCENE: {venue_type}
STRATEGY USED: {strategy_profile}

ZONES DISCOVERED: {n_zones}
{zone_summary}

The attached image shows all discovered zones overlaid on the camera view.

Evaluate:
1. Are the zone boundaries reasonable for this type of venue?
2. Are there obvious missed areas where people gather?
3. Are there redundant/overlapping zones that should be merged?
4. Is the number of zones reasonable?

Respond ONLY in JSON:
{{
    "accept": true,
    "issues": ["<any problems found>"],
    "suggestions": ["<improvements if any>"],
    "rerun_with_adjustments": null,
    "reasoning": "<2-3 sentences>"
}}

If zones look wrong, set "accept": false and provide adjusted parameters in "rerun_with_adjustments":
{{
    "accept": false,
    "rerun_with_adjustments": {{
        "stdbscan_spatial_eps_m": 3.0,
        "min_dwell_seconds": 5.0,
        "fusion_min_strategies": 1
    }},
    "reasoning": "Zones too few — relaxing parameters to capture more areas"
}}
"""

GATE3_CLASSIFICATION_REVIEW_PROMPT = """Review zone classifications from a CCTV analytics system.

SCENE: {venue_type}

ZONE CLASSIFICATIONS:
{classification_summary}

Check for:
1. Contradictions (e.g., scene is a parking garage but zone classified as "dining_area")
2. Low confidence classifications that need reclassification
3. Duplicate zone types that might be the same area split incorrectly
4. Zone types that don't make sense for this venue

Respond ONLY in JSON:
{{
    "accept": true,
    "reclassify": [],
    "reasoning": "<2-3 sentences>"
}}

If reclassification needed:
{{
    "accept": false,
    "reclassify": [
        {{"zone_id": "zone_001", "new_type": "corridor", "reason": "misclassified as seating"}}
    ],
    "reasoning": "Some zones contradict the venue type"
}}
"""
