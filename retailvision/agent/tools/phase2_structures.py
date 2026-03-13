"""Phase 2 Tool t12: VLM-based static structure detection.

Uses VLM to detect fixed structures (counters, tables, doorways) that
define zones regardless of whether people are present.
"""

from loguru import logger

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry
from agent.vlm.openrouter_client import OpenRouterVLM, encode_frame_to_b64
from agent.vlm.prompts import VLM_STRUCTURES_PROMPT


@ToolRegistry.register("vlm_detect_structures")
def vlm_detect_structures(state, config) -> ToolResult:
    """t12: Detect static structural elements from reference frame.

    These become structure-based zone candidates merged in Phase 3.
    Examples: shop counters, table clusters, doorways, barriers, kiosks.
    """
    if not config.openrouter_api_key:
        state.static_structures = []
        return ToolResult(
            success=True,
            message="OpenRouter API not configured, skipping structure detection",
            data={"n_structures": 0},
        )

    if state.reference_frame is None:
        return ToolResult(success=False, message="No reference frame available")

    vlm = OpenRouterVLM(
        config.openrouter_api_key,
        config.vlm_primary_model,
        config.vlm_fallback_model,
    )

    image_b64 = encode_frame_to_b64(state.reference_frame)
    result = vlm.query_with_image(image_b64, VLM_STRUCTURES_PROMPT)
    vlm.close()

    structures = result.get("structures", [])
    H, W = state.frame_shape[:2]

    # Convert normalized bbox to pixel coordinates
    for s in structures:
        bbox = s.get("bbox", [0, 0, 1, 1])
        s["bbox_pixel"] = [
            bbox[0] * W,
            bbox[1] * H,
            bbox[2] * W,
            bbox[3] * H,
        ]

    state.static_structures = structures

    return ToolResult(
        success=True,
        data={"n_structures": len(structures)},
        message=f"Detected {len(structures)} static structures via VLM",
    )
