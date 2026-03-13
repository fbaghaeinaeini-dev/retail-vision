"""Pipeline configuration with Pydantic validation."""

from pathlib import Path

from pydantic_settings import BaseSettings


class PipelineConfig(BaseSettings):
    """Configuration for Module B (Agent Pipeline)."""

    # API Keys
    openrouter_api_key: str = ""
    replicate_api_token: str = ""  # Optional — pipeline works without it

    # Paths
    db_path: Path = Path("data/retailvision.db")
    video_id: str = ""
    output_dir: Path = Path("output")

    # Calibration
    bev_resolution: float = 0.05  # meters per BEV pixel
    person_height_m: float = 1.7

    # VLM
    vlm_primary_model: str = "qwen/qwen3.5-35b-a3b"
    vlm_fallback_model: str = "qwen/qwen2.5-vl-7b-instruct"
    vlm_temperature: float = 0.2
    vlm_max_retries: int = 3
    vlm_confidence_threshold: float = 0.5
    vlm_crop_margin_pct: float = 0.20
    vlm_wide_margin_pct: float = 0.40

    # Zone Discovery
    dwell_speed_threshold_m_s: float = 0.5
    min_dwell_seconds: float = 10.0
    confinement_radius_m: float = 2.0
    min_curvature_rad: float = 0.5
    min_zone_area_m2: float = 1.0

    # ST-DBSCAN
    stdbscan_spatial_eps_m: float = 2.0
    stdbscan_temporal_eps_s: float = 60.0
    stdbscan_min_samples: int = 5

    # Occupancy Grid
    occupancy_grid_cell_m: float = 0.5
    occupancy_min_density: float = 0.1

    # Trajectory Graph
    traj_edge_weight_threshold: float = 3
    traj_resolution: float = 0.3

    # Fusion
    fusion_min_strategies: int = 2
    fusion_single_strategy_min_conf: float = 0.7

    # Fusion — zone merging
    merge_threshold_m2: float = 2.5
    merge_max_distance_m: float = 4.0
    max_zone_area_m2: float = 50.0

    # Quality
    quality_threshold: float = 0.40
    track_quality_threshold: float = 0.3

    # Temporal analytics
    temporal_bin_seconds: int = 300
    rush_multiplier: float = 2.0

    # Spatial analytics
    spatial_heatmap_cell_m: float = 0.5

    # Orchestrator
    max_phase2_retries: int = 2

    # Morphological cleanup (fusion)
    morph_close_kernel: int = 3
    morph_open_kernel: int = 3

    # Watershed splitting
    watershed_blur_kernel: int = 7
    watershed_dilate_kernel: int = 9
    watershed_min_confidence: float = 0.2

    model_config = {"env_file": ".env", "env_prefix": "", "extra": "ignore"}
