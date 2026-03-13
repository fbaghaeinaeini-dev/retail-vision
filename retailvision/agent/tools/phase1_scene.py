"""Phase 1 Tools: t04 (compute_track_stats) and t05 (vlm_scene_layout).

t04 computes tracking statistics (no hardcoded scene type classification).
t05 sends the frame to VLM for free-form scene understanding.
"""

from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM, encode_frame_to_b64
from agent.vlm.prompts import VLM_SCENE_LAYOUT_PROMPT


@ToolRegistry.register("classify_scene_type")
def classify_scene_type(state, config) -> ToolResult:
    """t04: Compute tracking statistics for downstream tools.

    Computes density, speed, and spatial metrics from tracking data.
    Does NOT hardcode a scene type — that is left to the VLM in vlm_scene_layout.
    """
    df = state.raw_tracks
    if df is None or df.empty:
        return ToolResult(success=False, message="No tracks available")

    n_tracks = df["track_id"].nunique()
    duration_min = state.video_duration_seconds / 60

    x_range = df["x_center"].max() - df["x_center"].min()
    y_range = df["y_center"].max() - df["y_center"].min()
    aspect = x_range / (y_range + 1e-6)

    if "speed_m_s" in df.columns:
        median_speed = float(df["speed_m_s"].median())
    elif "avg_speed_px_per_sec" in df.columns:
        median_speed = float(df["avg_speed_px_per_sec"].median())
    else:
        median_speed = 0.0

    density = n_tracks / max(duration_min, 1)

    # Store stats for LLM to use (no hardcoded scene type)
    state.adaptive_params = {
        "n_tracks": n_tracks,
        "density_tracks_per_min": round(density, 1),
        "median_speed_m_s": round(median_speed, 2),
        "spatial_aspect_ratio": round(float(aspect), 2),
        "duration_minutes": round(duration_min, 1),
    }

    return ToolResult(
        success=True,
        data=state.adaptive_params,
        message=f"Track stats: {n_tracks} tracks, {density:.1f}/min, speed {median_speed:.2f} m/s",
    )


@ToolRegistry.register("vlm_scene_layout")
def vlm_scene_layout(state, config) -> ToolResult:
    """t05: VLM full-frame scene layout analysis.

    Sends the reference frame to the VLM for spatial layout understanding.
    VLM decides the scene type freely (not from a preset enum).
    This output flows to ALL downstream tools as context.
    """
    if not config.openrouter_api_key:
        state.scene_layout = {"venue_type": "unknown", "areas": []}
        state.scene_type = "unknown"
        return ToolResult(
            success=True,
            message="No API key — scene type unknown",
            data={"vlm_available": False},
        )

    if state.reference_frame is None:
        return ToolResult(success=False, message="No reference frame available")

    vlm = OpenRouterVLM(
        config.openrouter_api_key,
        config.vlm_primary_model,
        config.vlm_fallback_model,
        config.vlm_temperature,
    )

    image_b64 = encode_frame_to_b64(state.reference_frame)
    result = vlm.query_with_image(image_b64, VLM_SCENE_LAYOUT_PROMPT)
    vlm.close()

    if result.get("parse_error"):
        state.scene_layout = {"venue_type": "unknown", "areas": []}
        state.scene_type = "unknown"
        return ToolResult(
            success=True,
            message="VLM parse failed — scene type unknown",
            data={"vlm_available": True, "parse_error": True},
        )

    state.scene_layout = result
    # Trust VLM's venue_type directly — no re-mapping to hardcoded enum
    state.scene_type = result.get("venue_type", "unknown")

    n_areas = len(result.get("areas", []))
    return ToolResult(
        success=True,
        data={"venue_type": state.scene_type, "n_areas": n_areas},
        message=f"Scene: {state.scene_type}, {n_areas} areas identified",
    )
