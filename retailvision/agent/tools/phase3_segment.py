"""Phase 3 Tool: Segmentation-based zone context using Semantic-Segment-Anything.

SSA runs once on the full scene and returns all labeled segments.
Instead of overriding zone types directly, SSA labels are stored as
additional context for the VLM classifier to reason about.
"""

import numpy as np
from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.replicate_client import ReplicateSegmentation


@ToolRegistry.register("segment_zone_refinement")
def segment_zone_refinement(state, config) -> ToolResult:
    """Gather semantic segmentation labels as context for VLM classification.

    Runs SSA once on the reference frame, then for each zone computes
    which semantic labels overlap. These labels are stored in
    state.zone_classifications[zid]["ssa_labels"] for the VLM classifier
    to use as additional evidence.
    """
    if not config.replicate_api_token:
        return ToolResult(
            success=True,
            message="Replicate API not configured, skipping segmentation",
            data={"refined": 0},
        )

    if state.reference_frame is None:
        return ToolResult(
            success=True,
            message="No reference frame for segmentation",
            data={"refined": 0},
        )

    seg = ReplicateSegmentation(config.replicate_api_token)
    H_img, W_img = state.reference_frame.shape[:2]

    # Single API call — SSA segments the entire scene
    segments = seg.segment_scene(state.reference_frame)

    if not segments:
        return ToolResult(
            success=True,
            message="SSA returned no segments",
            data={"refined": 0},
        )

    # Log discovered classes
    class_counts = {}
    for s in segments:
        name = s["class_name"]
        class_counts[name] = class_counts.get(name, 0) + 1
    logger.info(f"SSA classes found: {class_counts}")

    # Store raw segments in state
    state.scene_segment_masks = {
        "ssa_segments": segments,
        "class_counts": class_counts,
    }

    # For each zone, gather overlapping SSA semantic labels as context
    zones_with_labels = 0
    zones_source = state.fused_zones_dict or {}

    for zid, zone in zones_source.items():
        bbox = zone.get("bbox_pixel", [])
        if not bbox or len(bbox) < 4:
            continue

        x1, y1, x2, y2 = [int(b) for b in bbox]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W_img, x2), min(H_img, y2)

        zone_area_px = (x2 - x1) * (y2 - y1)
        if zone_area_px < 100:
            continue

        # Get raw semantic labels overlapping this zone
        labels = seg.get_semantic_labels_for_region(
            state.reference_frame, [x1, y1, x2, y2]
        )

        if labels:
            # Store as context for the VLM classifier (not as a decision)
            state.zone_classifications.setdefault(zid, {})
            state.zone_classifications[zid]["ssa_labels"] = labels
            zones_with_labels += 1

    return ToolResult(
        success=True,
        data={
            "zones_with_labels": zones_with_labels,
            "n_segments": len(segments),
            "classes": class_counts,
        },
        message=f"SSA provided labels for {zones_with_labels} zones "
                f"({len(segments)} segments, {len(class_counts)} classes)",
    )
