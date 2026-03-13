"""Agent pipeline state — carries all data between tools."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class AgentState:
    """Mutable state passed through all 26 pipeline tools.

    Organized by phase. Each tool reads what it needs and writes its outputs.
    """

    # ── Phase 1: Scene Understanding ──
    raw_tracks: pd.DataFrame | None = None
    reference_frame: np.ndarray | None = None
    reference_frame_idx: int = 0
    frame_shape: tuple = (0, 0, 3)

    # Calibration (from person-height regression, NOT depth)
    homography_matrix: np.ndarray | None = None  # 3x3 pixel→BEV
    bev_scale: float = 0.0                        # meters per BEV pixel
    bev_size: tuple = (0, 0)
    calibration_method: str = ""                   # "person_height" or "depth_enhanced"

    # Scene understanding
    scene_type: str = "unknown"
    scene_layout: dict = field(default_factory=dict)
    scene_depth_map: np.ndarray | None = None
    scene_depth_stats: dict = field(default_factory=dict)
    adaptive_params: dict = field(default_factory=dict)

    # ── Phase 2: Zone Discovery ──
    dwell_points: list = field(default_factory=list)
    zone_candidates_A: list = field(default_factory=list)  # ST-DBSCAN
    zone_candidates_B: list = field(default_factory=list)  # Occupancy grid
    zone_candidates_C: list = field(default_factory=list)  # Trajectory graph
    fused_zones: list = field(default_factory=list)
    fused_zones_dict: dict = field(default_factory=dict)
    static_structures: list = field(default_factory=list)

    # ── Phase 3: Zone Enrichment ──
    zone_crops: dict = field(default_factory=dict)
    zone_depth_info: dict = field(default_factory=dict)
    zone_objects: dict = field(default_factory=dict)
    zone_signage: dict = field(default_factory=dict)
    zone_classifications: dict = field(default_factory=dict)
    zone_descriptions: dict = field(default_factory=dict)
    zone_registry: dict = field(default_factory=dict)
    zone_registry_draft: dict = field(default_factory=dict)
    quick_zone_analytics: dict = field(default_factory=dict)

    # ── Phase 4: Analytics ──
    zone_analytics: dict = field(default_factory=dict)
    flow_analytics: dict = field(default_factory=dict)
    temporal_analytics: dict = field(default_factory=dict)
    spatial_analytics: dict = field(default_factory=dict)

    # ── Phase 5: Validation ──
    validation_metrics: dict = field(default_factory=dict)
    quality_passed: bool = False

    # ── Phase 6: Visualization ──
    visualization_plan: list = field(default_factory=list)

    # ── Meta ──
    video_id: str = ""
    video_duration_seconds: float = 0.0
    current_step: str = ""
    errors: list = field(default_factory=list)
    phase2_retry_count: int = 0
    tool_history: list = field(default_factory=list)  # [{tool, phase, success, message, duration}]

    # Segmentation masks (Phase 3)
    scene_segment_masks: dict = field(default_factory=dict)

    # Agentic: LLM-decided parameters and plans
    llm_chosen_params: dict = field(default_factory=dict)
    tool_plan: dict = field(default_factory=dict)  # {"phase2": [...], "phase3": [...]}
    llm_validation: dict = field(default_factory=dict)

    # Agentic: strategy profile and active tools
    strategy_profile: str = "general"
    active_phase2_tools: list = field(default_factory=list)
    active_phase3_tools: list = field(default_factory=list)
