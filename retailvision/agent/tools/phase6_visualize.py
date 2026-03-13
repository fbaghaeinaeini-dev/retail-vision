"""Phase 6 Tools: t26-t29 — Visualization planning, rendering, and export.

t26: plan_visualizations (agentic — LLM decides chart types)
t27: render_all_visualizations
t28: render_3d_scene
t29: export_dashboard_bundle
"""

import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM
from agent.vlm.prompts import VLM_VIZ_PLANNER_PROMPT


@ToolRegistry.register("plan_visualizations")
def plan_visualizations(state, config) -> ToolResult:
    """t26: Agentic visualization planning — LLM decides chart types."""
    # Default plan if no VLM available
    default_plan = [
        {"type": "zone_map_perspective", "priority": 1, "reason": "Primary spatial overview"},
        {"type": "zone_map_bev", "priority": 2, "reason": "Bird's eye view with metrics"},
        {"type": "heatmap_bev", "priority": 3, "reason": "Density distribution"},
        {"type": "zone_detail_cards", "priority": 4, "reason": "Per-zone summaries"},
        {"type": "bar_chart", "priority": 5, "reason": "Zone metric comparison"},
    ]

    if len(state.zone_registry) >= 3:
        default_plan.append(
            {"type": "sankey_flow", "priority": 6, "reason": "Zone-to-zone flows"}
        )
    default_plan.append(
        {"type": "temporal_heatmap", "priority": 7, "reason": "Time patterns"}
    )

    if not config.openrouter_api_key:
        state.visualization_plan = default_plan
        return ToolResult(
            success=True,
            data={"n_viz": len(default_plan)},
            message=f"Default viz plan: {len(default_plan)} visualizations",
        )

    # Ask LLM to plan
    vlm = OpenRouterVLM(config.openrouter_api_key, config.vlm_primary_model)

    zone_types = [z.get("zone_type", "unknown") for z in state.zone_registry.values()]
    prompt = VLM_VIZ_PLANNER_PROMPT.format(
        scene_type=state.scene_type,
        n_zones=len(state.zone_registry),
        zone_types_summary=", ".join(set(zone_types)),
        n_tracks=state.raw_tracks["track_id"].nunique() if state.raw_tracks is not None else 0,
        duration=f"{state.video_duration_seconds / 60:.0f} minutes",
        depth_status="available" if state.scene_depth_map is not None else "not available",
        key_findings="Zone discovery complete",
    )

    try:
        # Use text-only query for planning (no image needed)
        import httpx
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.vlm_primary_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        plan = json.loads(text) if text.strip().startswith("{") else {"visualizations": default_plan}
        state.visualization_plan = plan.get("visualizations", default_plan)
    except Exception as e:
        logger.warning(f"VLM viz planning failed: {e}, using defaults")
        state.visualization_plan = default_plan

    vlm.close()

    return ToolResult(
        success=True,
        data={"n_viz": len(state.visualization_plan)},
        message=f"Planned {len(state.visualization_plan)} visualizations",
    )


@ToolRegistry.register("render_all_visualizations")
def render_all_visualizations(state, config) -> ToolResult:
    """t27: Render all planned visualizations as images."""
    output_dir = Path(config.output_dir) / "zones"
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered = []

    # Always render zone map on reference frame
    if state.reference_frame is not None and state.zone_registry:
        zone_map = _render_zone_map_perspective(state)
        cv2.imwrite(str(output_dir / "zone_map_perspective.png"), zone_map)
        rendered.append("zone_map_perspective")

    # BEV zone map
    if state.zone_registry and state.homography_matrix is not None:
        bev_map = _render_zone_map_bev(state)
        cv2.imwrite(str(output_dir / "zone_map_bev.png"), bev_map)
        rendered.append("zone_map_bev")

    # Density heatmap
    if state.spatial_analytics.get("heatmap_density"):
        heatmap = _render_heatmap(state)
        cv2.imwrite(str(output_dir / "heatmap_bev.png"), heatmap)
        rendered.append("heatmap_bev")

    # Per-zone crop images from reference frame using bbox_pixel
    if state.reference_frame is not None and state.zone_registry:
        frame = state.reference_frame
        fH, fW = frame.shape[:2]
        margin = 0.20  # 20% margin around bbox
        for zid, zone in state.zone_registry.items():
            bbox = zone.get("bbox_pixel", [0, 0, fW, fH])
            x1, y1, x2, y2 = bbox
            w, h = x2 - x1, y2 - y1
            mx, my = w * margin, h * margin
            cx1 = max(0, int(x1 - mx))
            cy1 = max(0, int(y1 - my))
            cx2 = min(fW, int(x2 + mx))
            cy2 = min(fH, int(y2 + my))
            crop = frame[cy1:cy2, cx1:cx2]
            if crop.size > 0:
                cv2.imwrite(str(output_dir / f"{zid}_crop.png"), crop)
        rendered.append("zone_crops")

    return ToolResult(
        success=True,
        data={"rendered": rendered},
        message=f"Rendered {len(rendered)} visualizations",
    )


@ToolRegistry.register("render_3d_scene")
def render_3d_scene(state, config) -> ToolResult:
    """t28: Export 3D scene data for Three.js viewer."""
    output_dir = Path(config.output_dir)

    scene_3d = {
        "has_depth": state.scene_depth_map is not None,
        "zones": [],
        "camera": {
            "focal_length": state.scene_depth_stats.get("focal_length_from_depth"),
        },
    }

    for zid, zone in state.zone_registry.items():
        scene_3d["zones"].append({
            "zone_id": zid,
            "name": zone.get("business_name", zid),
            "type": zone.get("zone_type", "unknown"),
            "polygon_bev": zone.get("polygon_bev", []),
            "depth": zone.get("depth_info", {}).get("avg_depth_m"),
        })

    with open(output_dir / "3d_scene.json", "w") as f:
        json.dump(scene_3d, f, indent=2, default=str)

    return ToolResult(
        success=True,
        data={"has_depth": scene_3d["has_depth"]},
        message=f"3D scene exported ({len(scene_3d['zones'])} zones)",
    )


@ToolRegistry.register("export_dashboard_bundle")
def export_dashboard_bundle(state, config) -> ToolResult:
    """t29: Export complete dashboard data bundle as report.json."""
    output_dir = Path(config.output_dir)

    # Count tracks and detections for meta
    n_tracks = 0
    n_detections = 0
    if state.raw_tracks is not None:
        n_detections = len(state.raw_tracks)
        n_tracks = state.raw_tracks["track_id"].nunique() if "track_id" in state.raw_tracks.columns else 0

    report = {
        "meta": {
            "video_id": state.video_id,
            "scene_type": state.scene_type,
            "duration_seconds": state.video_duration_seconds,
            "calibration_method": state.calibration_method,
            "quality_passed": state.quality_passed,
            "validation_metrics": state.validation_metrics,
            "n_tracks": n_tracks,
            "n_detections": n_detections,
            "n_zones": len(state.zone_registry),
            "strategy_profile": state.strategy_profile,
            "llm_chosen_params": state.llm_chosen_params,
            "tool_history": state.tool_history,
        },
        "zones": {},
        "analytics": state.zone_analytics,
        "flow": state.flow_analytics,
        "temporal": {
            "time_bin_seconds": state.temporal_analytics.get("time_bin_seconds", 300),
            "occupancy_matrix": state.temporal_analytics.get("occupancy_matrix", {}),
        },
        "spatial": {
            "heatmap_bounds": state.spatial_analytics.get("heatmap_bounds", {}),
            "cell_size_m": state.spatial_analytics.get("cell_size_m", 0.5),
            "peak_density": state.spatial_analytics.get("peak_density", 0),
        },
        "visualization_plan": state.visualization_plan,
    }

    # Zones (exclude large binary data)
    for zid, zone in state.zone_registry.items():
        report["zones"][zid] = {
            k: v for k, v in zone.items()
            if k not in ("crops",)
        }

    with open(output_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Save zone registry to DB
    from tracker.database import TrackDatabase
    db = TrackDatabase(config.db_path)
    db.save_zones(state.video_id, state.zone_registry)
    if state.zone_analytics:
        db.save_zone_analytics(state.zone_analytics)
    if state.flow_analytics.get("transitions"):
        db.save_zone_transitions(state.flow_analytics["transitions"])
    db.close()

    return ToolResult(
        success=True,
        data={"report_path": str(output_dir / "report.json")},
        message=f"Dashboard bundle exported: {len(report['zones'])} zones, "
                f"{output_dir / 'report.json'}",
    )


# ── Rendering helpers ──

def _render_zone_map_perspective(state) -> np.ndarray:
    """Draw zone polygons overlaid on the camera reference frame."""
    frame = state.reference_frame.copy()

    for zid, zone in state.zone_registry.items():
        polygon = zone.get("polygon_pixel", [])
        if not polygon or len(polygon) < 3:
            bbox = zone.get("bbox_pixel", [])
            if bbox:
                polygon = [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]]
            else:
                continue

        pts = np.array(polygon, dtype=np.int32)
        color = _zone_color(zone.get("zone_type", ""))

        # Semi-transparent fill
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color)
        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)

        # Border
        cv2.polylines(frame, [pts], True, color, 2)

        # Label
        cx = int(np.mean(pts[:, 0]))
        cy = int(np.mean(pts[:, 1]))
        label = zone.get("business_name", zid)
        cv2.putText(frame, label, (cx - 30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return frame


def _render_zone_map_bev(state) -> np.ndarray:
    """Render BEV zone map."""
    bev_w, bev_h = state.bev_size
    bev_w = min(bev_w, 1500)
    bev_h = min(bev_h, 1500)

    canvas = np.full((bev_h, bev_w, 3), 20, dtype=np.uint8)

    for zid, zone in state.zone_registry.items():
        polygon = zone.get("polygon_bev", [])
        if not polygon or len(polygon) < 3:
            continue

        pts = (np.array(polygon) / state.bev_scale).astype(np.int32)
        color = _zone_color(zone.get("zone_type", ""))

        cv2.fillPoly(canvas, [pts], tuple(c // 3 for c in color))
        cv2.polylines(canvas, [pts], True, color, 2)

    # Flip 180° so the near-camera side is at the bottom (matching camera perspective)
    canvas = cv2.flip(canvas, -1)

    return canvas


def _render_heatmap(state) -> np.ndarray:
    """Render BEV density heatmap."""
    data = state.spatial_analytics.get("heatmap_density", [])
    if not data:
        return np.zeros((100, 100, 3), dtype=np.uint8)

    heatmap = np.array(data, dtype=np.float32)
    if heatmap.max() > 0:
        normalized = (heatmap / heatmap.max() * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(heatmap, dtype=np.uint8)

    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)
    return colored


def _zone_color(zone_type: str) -> tuple[int, int, int]:
    """Deterministic color for any free-form zone type string.

    Uses the same hash-based palette as the dashboard (colors.js)
    so backend-rendered images match the frontend visuals.
    """
    # BGR palette (matching dashboard hex PALETTE converted to BGR)
    PALETTE = [
        (53, 107, 255),   # #ff6b35
        (255, 157, 51),   # #339dff
        (136, 255, 0),    # #00ff88
        (255, 102, 179),  # #b366ff
        (51, 194, 255),   # #ffc233
        (0, 149, 255),    # #ff9500
        (255, 212, 0),    # #00d4ff
        (102, 51, 255),   # #ff3366
        (0, 204, 136),    # #88cc00
        (153, 102, 204),  # #cc6699
        (255, 157, 74),   # #4a9dff
        (102, 136, 255),  # #ff8866
        (170, 204, 51),   # #33ccaa
        (255, 102, 153),  # #9966ff
        (51, 170, 221),   # #ddaa33
    ]
    if not zone_type or zone_type == "unknown":
        return (78, 58, 58)
    h = 0
    for c in zone_type:
        h = ((h << 5) - h + ord(c)) & 0xFFFFFFFF
    return PALETTE[h % len(PALETTE)]
