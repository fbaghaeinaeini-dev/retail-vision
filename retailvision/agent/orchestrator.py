"""Zone Discovery Agent — hybrid ReAct orchestrator.

Architecture: Fixed phases with 3 LLM decision gates between them.
- Phase 1: Always runs (scene understanding)
- GATE 1: LLM decides strategy profile, all parameters, tool plan
- Phase 2: Runs LLM-selected strategy tools
- GATE 2: LLM reviews discovered zones, may trigger re-run
- Phase 3a: Quick analytics (behavioral data for classifier)
- Phase 3b: LLM-selected enrichment tools
- GATE 3: LLM reviews classifications, may reclassify
- Phase 4-6: Always runs (analytics, validation, visualization)
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from loguru import logger

from agent.config import PipelineConfig
from agent.gates import (
    apply_gate1_decision,
    apply_gate2_decision,
    apply_gate3_decision,
    run_gate1_strategy,
    run_gate2_zone_review,
    run_gate3_classification_review,
)
from agent.models import ToolResult
from agent.state import AgentState
from agent.strategy_profiles import get_profile
from agent.tools.registry import ToolRegistry

# Import all tool modules so they register themselves
import agent.tools.phase1_ingest            # noqa: F401
import agent.tools.phase1_calibrate         # noqa: F401
import agent.tools.phase1_scene             # noqa: F401
import agent.tools.phase1_depth             # noqa: F401
import agent.tools.phase1_llm_params        # noqa: F401
import agent.tools.phase2_dwell             # noqa: F401
import agent.tools.phase2_strategy_a        # noqa: F401
import agent.tools.phase2_strategy_b        # noqa: F401
import agent.tools.phase2_strategy_c        # noqa: F401
import agent.tools.phase2_fusion            # noqa: F401
import agent.tools.phase2_structures        # noqa: F401
import agent.tools.phase3_crop              # noqa: F401
import agent.tools.phase3_depth_zones       # noqa: F401
import agent.tools.phase3_vlm_objects       # noqa: F401
import agent.tools.phase3_vlm_signage       # noqa: F401
import agent.tools.phase3_vlm_classify      # noqa: F401
import agent.tools.phase3_vlm_describe      # noqa: F401
import agent.tools.phase3_segment           # noqa: F401
import agent.tools.phase3_merge             # noqa: F401
import agent.tools.phase3_quick_analytics   # noqa: F401
import agent.tools.phase4_analytics         # noqa: F401
import agent.tools.phase5_validate          # noqa: F401
import agent.tools.phase6_visualize         # noqa: F401

# Phase definitions — tools grouped by phase
PHASE1_TOOLS = [
    "ingest_from_db",
    "extract_reference_frame",
    "calibrate_from_person_height",
    "classify_scene_type",
    "vlm_scene_layout",
    "depth_scene_analysis",
]

# Phase 2 and 3 tools are selected dynamically by Gate 1 from strategy profiles

PHASE4_TOOLS = [
    "compute_zone_analytics",
    "compute_flow_analytics",
    "compute_temporal_analytics",
    "compute_spatial_analytics",
]

PHASE5_TOOLS = [
    "validate_zones",
    "quality_gate",
]

PHASE6_TOOLS = [
    "plan_visualizations",
    "render_all_visualizations",
    "render_3d_scene",
    "export_dashboard_bundle",
]


class ZoneDiscoveryAgent:
    """Hybrid ReAct orchestrator — fixed phases with LLM decision gates."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.state = AgentState()
        self.history: list[dict] = []
        self.run_id = str(uuid.uuid4())[:8]

        self.output_dir = Path(config.output_dir)
        self.debug_dir = self.output_dir / "debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "zones").mkdir(parents=True, exist_ok=True)

    def run(self) -> AgentState:
        """Execute the hybrid ReAct pipeline."""
        logger.info(f"=== Pipeline run {self.run_id} starting ===")
        logger.info(f"Registered tools: {ToolRegistry.list_tools()}")
        start_time = datetime.now(timezone.utc)

        # ── Phase 1: Scene Understanding (always runs) ──
        self._run_phase("Phase 1: Scene Understanding", PHASE1_TOOLS, phase=1)

        # ── GATE 1: LLM Strategy Decision ──
        self._run_gate_logged("gate1_strategy", 1, self._execute_gate1)

        # ── Phase 2: Zone Discovery (LLM-selected tools) ──
        self._run_phase(
            "Phase 2: Zone Discovery",
            self.state.active_phase2_tools,
            phase=2,
        )

        # ── GATE 2: LLM Zone Review ──
        rerun = self._run_gate_logged("gate2_zone_review", 2, self._execute_gate2)
        if rerun:
            self._run_phase(
                "Phase 2 (retry): Zone Discovery",
                self.state.active_phase2_tools,
                phase=2,
            )

        # ── Phase 3a: Quick Analytics (for classifier context) ──
        self._run_phase(
            "Phase 3a: Quick Analytics",
            ["crop_zone_images", "compute_quick_zone_analytics"],
            phase=3,
        )

        # ── Phase 3b: Enrichment (LLM-selected tools, minus crop and merge) ──
        enrichment_tools = [
            t for t in self.state.active_phase3_tools
            if t not in ("crop_zone_images", "merge_zone_registry")
        ]
        self._run_phase("Phase 3b: Zone Enrichment", enrichment_tools, phase=3)

        # ── Phase 3c: Merge registry ──
        self._run_phase("Phase 3c: Merge Registry", ["merge_zone_registry"], phase=3)

        # ── GATE 3: LLM Classification Review ──
        self._run_gate_logged("gate3_classification_review", 3, self._execute_gate3)

        # ── Phase 4: Analytics (always runs) ──
        self._run_phase("Phase 4: Analytics", PHASE4_TOOLS, phase=4)

        # ── Phase 5: Validation (always runs) ──
        self._run_phase("Phase 5: Validation", PHASE5_TOOLS, phase=5)

        # Handle quality gate re-run
        last_entry = self.history[-1] if self.history else {}
        if (last_entry.get("tool") == "quality_gate"
                and isinstance(last_entry.get("data"), dict)
                and last_entry["data"].get("retry")
                and self.state.phase2_retry_count < self.config.max_phase2_retries):
            logger.warning("Quality gate triggered Phase 2 re-run")
            self._quality_gate_rerun(enrichment_tools)

        # ── Phase 6: Visualization & Export (always runs) ──
        self._run_phase("Phase 6: Visualization", PHASE6_TOOLS, phase=6)

        end_time = datetime.now(timezone.utc)
        total = (end_time - start_time).total_seconds()
        logger.success(
            f"=== Pipeline complete: {len(self.state.zone_registry)} zones in {total:.0f}s ==="
        )
        return self.state

    # ── Phase execution ──

    def _run_phase(self, phase_name: str, tools: list[str], phase: int) -> None:
        """Execute a list of tools sequentially."""
        logger.info(f"── {phase_name} ({len(tools)} tools) ──")
        for tool_name in tools:
            if not ToolRegistry.has(tool_name):
                logger.warning(f"Tool '{tool_name}' not registered, skipping")
                continue
            self._execute_tool(tool_name, phase)

    def _execute_tool(self, tool_name: str, phase: int) -> ToolResult:
        """Execute a single tool with retry and logging."""
        self.state.current_step = tool_name
        logger.info(f"[Phase {phase}] Running: {tool_name}")
        t0 = time.time()

        try:
            result = self._execute_with_retry(tool_name, retries=2)
        except Exception as e:
            logger.error(f"{tool_name} failed: {e}")
            result = ToolResult(success=False, message=str(e))
            self.state.errors.append(f"{tool_name}: {e}")
            if phase <= 2:
                raise

        result.duration_seconds = time.time() - t0
        entry = {
            "tool": tool_name,
            "phase": phase,
            "success": result.success,
            "message": result.message,
            "duration": result.duration_seconds,
            "data": result.data if isinstance(result.data, dict) else None,
        }
        self.history.append(entry)
        self.state.tool_history.append(entry)

        logger.info(f"  -> {tool_name}: {result.message} ({result.duration_seconds:.1f}s)")

        if result.debug_artifacts:
            self._save_debug(tool_name, result.debug_artifacts)

        return result

    def _execute_with_retry(self, tool_name: str, retries: int = 2) -> ToolResult:
        """Execute a tool with retries on failure."""
        last_error = None
        for attempt in range(retries + 1):
            try:
                return ToolRegistry.execute(tool_name, self.state, self.config)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    logger.warning(f"  Retry {attempt + 1}/{retries} for {tool_name}: {e}")
                    time.sleep(1)
        raise last_error

    # ── Gate execution ──

    def _run_gate_logged(self, gate_name: str, phase: int, gate_fn) -> any:
        """Run a decision gate and log it as a tool entry."""
        logger.info(f"── GATE: {gate_name} ──")
        t0 = time.time()
        try:
            result = gate_fn()
            duration = time.time() - t0
            entry = {
                "tool": gate_name,
                "phase": phase,
                "success": True,
                "message": "Gate decision completed",
                "duration": duration,
                "is_gate": True,
            }
            self.history.append(entry)
            self.state.tool_history.append(entry)
            logger.info(f"  -> {gate_name}: completed ({duration:.1f}s)")
            return result
        except Exception as e:
            duration = time.time() - t0
            logger.warning(f"Gate {gate_name} failed: {e}, using defaults")
            entry = {
                "tool": gate_name,
                "phase": phase,
                "success": False,
                "message": f"Gate failed: {e}",
                "duration": duration,
                "is_gate": True,
            }
            self.history.append(entry)
            self.state.tool_history.append(entry)
            return None

    def _execute_gate1(self):
        """Gate 1: Strategy selection."""
        decision = run_gate1_strategy(self.state, self.config)
        apply_gate1_decision(decision, self.state, self.config)

        # If no active tools set (e.g., no API key), use general profile
        if not self.state.active_phase2_tools:
            profile = get_profile("general")
            self.state.active_phase2_tools = list(profile["phase2_tools"])
            self.state.active_phase3_tools = list(profile["phase3_tools"])
            self.state.strategy_profile = "general"

    def _execute_gate2(self) -> bool:
        """Gate 2: Zone review. Returns True if Phase 2 re-run needed."""
        decision = run_gate2_zone_review(self.state, self.config)
        return apply_gate2_decision(decision, self.state, self.config)

    def _execute_gate3(self):
        """Gate 3: Classification review."""
        decision = run_gate3_classification_review(self.state, self.config)
        apply_gate3_decision(decision, self.state)

    # ── Quality gate re-run ──

    def _quality_gate_rerun(self, enrichment_tools: list[str]):
        """Re-run from Phase 2 through Phase 5 with relaxed parameters."""
        self.state.phase2_retry_count += 1
        self.config.stdbscan_spatial_eps_m *= 1.3
        self.config.min_dwell_seconds *= 0.8
        self.config.fusion_min_strategies = 1

        self._run_phase("Phase 2 (quality retry)", self.state.active_phase2_tools, phase=2)
        self._run_phase(
            "Phase 3 (quality retry)",
            ["crop_zone_images", "compute_quick_zone_analytics"] + enrichment_tools + ["merge_zone_registry"],
            phase=3,
        )
        self._run_phase("Phase 4 (quality retry)", PHASE4_TOOLS, phase=4)
        self._run_phase("Phase 5 (quality retry)", PHASE5_TOOLS, phase=5)

    # ── Debug & reporting ──

    def _save_debug(self, tool_name: str, artifacts: dict):
        """Save debug artifacts to disk."""
        import cv2
        for name, data in artifacts.items():
            path = self.debug_dir / f"{tool_name}__{name}"
            if isinstance(data, np.ndarray) and data.ndim in (2, 3):
                cv2.imwrite(str(path) + ".png", data)
            elif isinstance(data, (dict, list)):
                with open(str(path) + ".json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
            elif isinstance(data, str):
                with open(str(path) + ".txt", "w") as f:
                    f.write(data)

    def get_report(self) -> dict:
        """Generate summary report of the pipeline run."""
        return {
            "run_id": self.run_id,
            "video_id": self.state.video_id,
            "n_zones": len(self.state.zone_registry),
            "calibration_method": self.state.calibration_method,
            "scene_type": self.state.scene_type,
            "quality_passed": self.state.quality_passed,
            "validation_metrics": self.state.validation_metrics,
            "strategy_profile": self.state.strategy_profile,
            "llm_chosen_params": self.state.llm_chosen_params,
            "errors": self.state.errors,
            "tool_history": self.history,
        }
