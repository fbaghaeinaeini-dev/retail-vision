# RETAILVISION — Definitive Implementation Specification v4
# Agentic Zone Discovery Pipeline for CCTV Retail Analytics
# Single-file reference for Claude Code implementation

> **This is the SOLE implementation reference.** A coding agent reads this
> file and implements the entire system with no ambiguity. Every tool has
> defined I/O, every file has a path, every algorithm has pseudocode.

---

## TABLE OF CONTENTS

1. Design Principles & Architecture Decisions
2. System Architecture (3 Modules)
3. Module A: Offline Tracker (YOLOv26 + BoTSORT → SQLite)
4. Module B: Agent Pipeline (26 Tools across 6 Phases)
5. Module C: Dashboard (React + D3 + Three.js)
6. Database Schema
7. External API Integration
8. Configuration System
9. Testing & Validation Framework
10. File Structure
11. Implementation Order (20 days)
12. Appendix: Algorithm Pseudocode

---

## 1. DESIGN PRINCIPLES & ARCHITECTURE DECISIONS

### 1.1 Critical Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Depth NOT in tracker** | Depth is a Module B analysis tool only. Runs on reference frame + zone crops. NOT per-frame. | Tracker must work offline without API calls. Depth is expensive (~$0.01/call) and unnecessary per-frame for fixed camera. A single depth map of the scene + depth on zone crops is sufficient for spatial understanding. |
| **Calibration from tracking data** | Primary BEV calibration uses person-height regression from bbox data. Depth on reference frame is optional enhancement. | Every CCTV video has people walking → we always have bbox heights at various positions. This gives ground-plane geometry without any external API. More robust than relying on a single depth map. |
| **VLM as multi-purpose tool** | VLM is not just a "verifier." It's a full toolkit: scene analysis, object inventory, zone classification, spatial reasoning, description generation. | Qwen3.5 with native vision can identify objects (tables, counters, menu boards), read signage, estimate relative sizes, and reason about spatial layout. These are all distinct tools with specialized prompts, not one monolithic call. |
| **Ensemble zone discovery** | 3 strategies + fusion voting | No single clustering algorithm generalizes across indoor food courts, outdoor plazas, corridors, and mixed scenes. |
| **BEV-first spatial analysis** | All clustering, distance, and area calculations in meters on ground plane | Pixel distances are meaningless in perspective projection. A 2m table near camera = 200px. Same table far away = 40px. |
| **Scene-adaptive parameters** | Auto-classify scene type → load tuned parameter profile | Same eps that works in a dense food court produces 0 clusters in an outdoor parking lot. |
| **Agentic self-validation** | Pipeline computes quality metrics and can re-run zone discovery with adjusted parameters | Without validation, there's no way to know if output is useful. Agent self-corrects. |

### 1.2 Core Principles

```
P1: TRACKER IS PURE & OFFLINE
    Module A has ZERO external API dependencies. It runs YOLOv26 + BoTSORT
    locally, writes to SQLite. No depth, no VLM, no network calls.
    This ensures it works on air-gapped systems and processes video fast.

P2: DEPTH IS A KNOWLEDGE TOOL, NOT A TRACKING TOOL
    Depth estimation (via Replicate) runs ONCE on the reference frame and
    ONCE per zone crop. It provides spatial knowledge:
    - Scene depth map → ground plane understanding
    - Zone crops → physical size estimation for VLM context
    Total: ~15 Replicate calls per pipeline run, not thousands.

P3: VLM IS A SWISS-ARMY TOOLKIT
    Each VLM call has a specialized prompt for a specific task:
    - Scene layout analysis (full frame)
    - Object inventory (zone crop → list every visible object)
    - Zone classification (crop + behavioral data → zone type)
    - Signage reading (crop → extract text from signs/menus)
    - Spatial reasoning (crop + depth → estimate physical dimensions)
    - Zone description (all above → rich text description)
    Each is a separate tool with distinct prompt engineering.

P4: BEV-FIRST SPATIAL ANALYSIS
    All spatial work in metric ground-plane coordinates.
    Primary calibration: person-height regression (no API needed).
    Enhancement: single depth map on reference frame (1 API call).

P5: ENSEMBLE > SINGLE METHOD
    3 zone discovery strategies + fusion voting.

P6: EVERY TOOL PRODUCES DEBUG VISUALIZATION
    Non-negotiable. Stored in output/debug/.

P7: MODULAR & TESTABLE
    Pure function tools: (state, config) → ToolResult.
    Unit tests with synthetic fixtures for every tool.
```

---

## 2. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MODULE A: OFFLINE TRACKER (No API calls)             │
│                                                                         │
│  Video.mp4 ──▶ YOLOv26m ──▶ BoTSORT ──▶ Track Metadata ──▶ SQLite DB │
│                                                                         │
│  Also extracts: keyframes, track quality scores, per-track summaries   │
│  Does NOT do: depth estimation, VLM calls, any network requests        │
└──────────────────────────────────────────┬──────────────────────────────┘
                                           │
┌──────────────────────────────────────────┼──────────────────────────────┐
│                MODULE B: AGENT PIPELINE (26 Tools, 6 Phases)           │
│                                          ▼                              │
│  PHASE 1: Scene Understanding                                          │
│    ├─ Ingest tracks from DB                                            │
│    ├─ Calibrate camera (person-height regression → BEV)                │
│    ├─ Classify scene type (indoor/outdoor/corridor)                    │
│    ├─ VLM: Scene layout prior (full frame analysis)                    │
│    └─ Depth: Scene depth map (Replicate, 1 call) → spatial context    │
│                                                                         │
│  PHASE 2: Zone Discovery (Ensemble)                                    │
│    ├─ Dwell detection (BEV meters, confinement filter)                 │
│    ├─ Strategy A: Dwell ST-DBSCAN                                      │
│    ├─ Strategy B: Occupancy grid + connected components                │
│    ├─ Strategy C: Trajectory graph community detection                 │
│    ├─ Fusion: Weighted spatial voting                                   │
│    └─ VLM: Detect static structures from reference frame               │
│                                                                         │
│  PHASE 3: Zone Enrichment (VLM Toolkit)                                │
│    ├─ Crop zone images (standard + wide margin)                        │
│    ├─ Depth: Zone crops (Replicate, 1 per zone) → physical sizing     │
│    ├─ VLM Tool: Object inventory per zone                              │
│    ├─ VLM Tool: Zone classification (objects + behavior → type)        │
│    ├─ VLM Tool: Signage reader (extract text from crops)               │
│    ├─ VLM Tool: Zone describer (generate rich descriptions)            │
│    └─ Merge all data → final ZoneRegistry                              │
│                                                                         │
│  PHASE 4: Analytics                                                     │
│    ├─ Per-zone: visits, dwell, demographics, peak hours                │
│    ├─ Transitions: zone→zone flows, Sankey data, top paths             │
│    ├─ Temporal: occupancy time series, rush detection, correlation     │
│    └─ Spatial: BEV density heatmap, depth-informed metrics             │
│                                                                         │
│  PHASE 5: Validation                                                    │
│    ├─ Silhouette, coverage, temporal stability, VLM agreement          │
│    └─ Quality gate: re-run Phase 2 if below threshold                  │
│                                                                         │
│  PHASE 6: Visualization & Export                                        │
│    ├─ Agentic viz planner (LLM decides chart types)                    │
│    ├─ Render all visualizations                                         │
│    ├─ 3D scene export (Three.js data)                                  │
│    └─ Dashboard data bundle (report.json)                              │
│                                                                         │
│  External APIs used by Module B:                                        │
│    ☁️ OpenRouter (Qwen3.5 VLM) — ~20 calls per run                   │
│    ☁️ Replicate (Depth Pro) — ~15 calls per run                       │
└──────────────────────────────────────────┬──────────────────────────────┘
                                           │
┌──────────────────────────────────────────┼──────────────────────────────┐
│                MODULE C: REACT DASHBOARD                                │
│                                          ▼                              │
│  KPIs │ Zone Map │ BEV Map │ Sankey │ Heatmap │ 3D View │ Replay │ Debug│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MODULE A: OFFLINE TRACKER

### 3.1 Design: Pure Offline, Zero API Dependencies

Module A processes raw CCTV video into structured tracking data. It runs
entirely locally with no network calls. Output is a SQLite database.

### 3.2 Detector-Tracker

```python
# FILE: tracker/detector.py

from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path

class RetailTracker:
    """
    YOLOv26m + BoTSORT detector-tracker for CCTV.
    
    Key design choices:
    - yolo26m.pt: medium model, good balance for 1080p CCTV
    - imgsz=1280: higher res catches distant/small people
    - conf=0.25: lower threshold for CCTV (people often small/distant)
    - BoTSORT with ReID: handles occlusion in crowded retail
    - track_buffer=90: 3s persistence for brief disappearances
    - Batch DB inserts every 2000 detections for performance
    - Keyframe extraction every N frames for downstream analysis
    """
    
    def __init__(self, config):
        self.model = YOLO(config.yolo_model)  # "yolo26m.pt"
        self.config = config
        self.db = TrackDatabase(config.db_path)
    
    def process_video(self, video_path: str, video_id: str) -> dict:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.db.insert_video(video_id, video_path, fps, total_frames, W, H)
        
        frame_idx = 0
        batch = []
        
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            
            results = self.model.track(
                frame, persist=True,
                tracker=self.config.tracker_yaml,
                classes=self.config.detect_classes,  # [0] = person
                conf=self.config.detection_conf,     # 0.25
                iou=self.config.detection_iou,       # 0.5
                imgsz=self.config.imgsz,             # 1280
                verbose=False
            )
            
            if results[0].boxes.id is not None:
                boxes = results[0].boxes
                ids = boxes.id.int().cpu().numpy()
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy()
                
                for i, tid in enumerate(ids):
                    x1, y1, x2, y2 = xyxy[i]
                    batch.append({
                        "video_id": video_id,
                        "frame_idx": frame_idx,
                        "timestamp": frame_idx / fps,
                        "track_id": int(tid),
                        "x_center": (x1 + x2) / 2,
                        "y_center": (y1 + y2) / 2,
                        "bbox_x1": float(x1), "bbox_y1": float(y1),
                        "bbox_x2": float(x2), "bbox_y2": float(y2),
                        "bbox_w": float(x2 - x1), "bbox_h": float(y2 - y1),
                        "confidence": float(confs[i]),
                        "object_class": "person"
                    })
            
            # Extract keyframe (for VLM/depth analysis downstream)
            if frame_idx % self.config.keyframe_interval == 0:
                self.db.insert_keyframe(video_id, frame_idx, frame)
            
            if len(batch) >= 2000:
                self.db.insert_detections_batch(batch)
                batch = []
            
            frame_idx += 1
        
        if batch:
            self.db.insert_detections_batch(batch)
        cap.release()
        
        # Post-processing
        self.db.compute_track_summaries(video_id)
        self._score_track_quality(video_id)
        
        return {"frames_processed": frame_idx, "video_id": video_id}
    
    def _score_track_quality(self, video_id: str):
        """
        Quality score per track: [0, 1].
        
        Factors:
        - duration_score: min(duration_sec / 30, 1)
        - count_score: min(num_detections / 50, 1)
        - conf_score: avg detection confidence
        - completeness: detected_frames / duration_frames
        - smoothness: 1 - (std(displacement) / mean(displacement))
        
        Tracks with quality < 0.3 are filtered out by the agent pipeline.
        """
        tracks = self.db.get_track_summaries(video_id)
        for t in tracks:
            dur = min(t["duration_seconds"] / 30.0, 1.0)
            cnt = min(t["num_detections"] / 50.0, 1.0)
            conf = t["avg_confidence"]
            comp = t["num_detections"] / max(t["duration_frames"], 1)
            
            disps = self.db.get_track_displacements(video_id, t["track_id"])
            if len(disps) > 2:
                smooth = max(0, 1.0 - np.std(disps) / (np.mean(disps) + 1e-6))
            else:
                smooth = 0.5
            
            quality = 0.25*dur + 0.20*cnt + 0.20*conf + 0.15*comp + 0.20*smooth
            self.db.update_track_quality(video_id, t["track_id"], quality)
```

### 3.3 BoTSORT Config (Retail Tuned)

```yaml
# FILE: tracker/botsort_retail.yaml
tracker_type: botsort
track_high_thresh: 0.25
track_low_thresh: 0.1
new_track_thresh: 0.25
track_buffer: 90           # 3s at 30fps — handles CCTV occlusions
match_thresh: 0.8
fuse_score: true
with_reid: true            # Identity preservation across occlusions
model: "auto"              # YOLOv26 native features for ReID
gmc_method: sparseOptFlow  # Minimal for fixed camera
proximity_thresh: 0.5
appearance_thresh: 0.25
```

### 3.4 CLI

```bash
python scripts/run_tracker.py \
  --video data/footage.mp4 \
  --db data/retailvision.db \
  --model yolo26m.pt \
  --keyframe-interval 150
# No --depth flag. Depth happens later in Module B.
```

---

## 4. MODULE B: AGENT PIPELINE (26 Tools, 6 Phases)

### 4.1 Complete Tool Registry

```python
PIPELINE = [
    # ═══════ PHASE 1: Scene Understanding (6 tools) ═══════
    ("ingest_from_db",              {"phase": 1}),  # t01
    ("extract_reference_frame",     {"phase": 1}),  # t02
    ("calibrate_from_person_height",{"phase": 1}),  # t03 — BEV from bbox data
    ("classify_scene_type",         {"phase": 1}),  # t04 — adaptive params
    ("vlm_scene_layout",            {"phase": 1}),  # t05 — full-frame VLM
    ("depth_scene_analysis",        {"phase": 1}),  # t06 — Replicate, 1 call

    # ═══════ PHASE 2: Zone Discovery (6 tools) ═══════
    ("compute_dwell_points",        {"phase": 2}),  # t07
    ("strategy_dwell_clustering",   {"phase": 2}),  # t08 — ST-DBSCAN
    ("strategy_occupancy_grid",     {"phase": 2}),  # t09 — grid density
    ("strategy_trajectory_graph",   {"phase": 2}),  # t10 — Louvain communities
    ("fuse_zone_candidates",        {"phase": 2}),  # t11 — ensemble voting
    ("vlm_detect_structures",       {"phase": 2}),  # t12 — static furniture/counters

    # ═══════ PHASE 3: Zone Enrichment — VLM Toolkit (7 tools) ═══════
    ("crop_zone_images",            {"phase": 3}),  # t13
    ("depth_zone_analysis",         {"phase": 3}),  # t14 — Replicate per zone crop
    ("vlm_object_inventory",        {"phase": 3}),  # t15 — detect all objects in zone
    ("vlm_signage_reader",          {"phase": 3}),  # t16 — extract text/signs
    ("vlm_zone_classifier",         {"phase": 3}),  # t17 — type from objects+behavior
    ("vlm_zone_describer",          {"phase": 3}),  # t18 — rich text description
    ("merge_zone_registry",         {"phase": 3}),  # t19 — combine everything

    # ═══════ PHASE 4: Analytics (4 tools) ═══════
    ("compute_zone_analytics",      {"phase": 4}),  # t20
    ("compute_flow_analytics",      {"phase": 4}),  # t21
    ("compute_temporal_analytics",  {"phase": 4}),  # t22
    ("compute_spatial_analytics",   {"phase": 4}),  # t23

    # ═══════ PHASE 5: Validation (2 tools) ═══════
    ("validate_zones",              {"phase": 5}),  # t24
    ("quality_gate",                {"phase": 5}),  # t25 — agentic re-run

    # ═══════ PHASE 6: Visualization & Export (4 tools) ═══════
    ("plan_visualizations",         {"phase": 6}),  # t26 — agentic viz planning
    ("render_all_visualizations",   {"phase": 6}),  # t27
    ("render_3d_scene",             {"phase": 6}),  # t28
    ("export_dashboard_bundle",     {"phase": 6}),  # t29
]
```

### 4.2 Agent Orchestrator

```python
# FILE: agent/orchestrator.py

from dataclasses import dataclass, field
from typing import Any
import time, json
from loguru import logger

@dataclass
class ToolResult:
    success: bool
    data: Any = None
    debug_artifacts: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    duration_seconds: float = 0.0

class ZoneDiscoveryAgent:
    """
    Custom ReACT-style orchestrator with 26 tools across 6 phases.
    
    Agentic behavior:
    1. Phase 1: Scene classification adapts all downstream parameters
    2. Phase 3: VLM toolkit — multiple specialized tools, not one monolith
    3. Phase 5: Validation can trigger Phase 2 re-run with adjusted params
    4. Phase 6: LLM plans visualization strategy based on data shape
    
    Non-agentic: tool sequence within phases is deterministic.
    """
    
    MAX_PHASE2_RETRIES = 2
    
    def __init__(self, config):
        self.config = config
        self.state = AgentState()
        self.tools = ToolRegistry()
        self.history = []
    
    def run(self):
        for tool_name, meta in self.PIPELINE:
            self.state.current_step = tool_name
            logger.info(f"[Phase {meta['phase']}] {tool_name}")
            
            t0 = time.time()
            try:
                result = self._execute_with_retry(tool_name, retries=2)
            except Exception as e:
                logger.error(f"{tool_name} failed: {e}")
                result = ToolResult(success=False, message=str(e))
                self.state.errors.append(f"{tool_name}: {e}")
                if meta["phase"] <= 2:  # Critical phases abort on failure
                    raise
            
            result.duration_seconds = time.time() - t0
            self.history.append({"tool": tool_name, "result": result})
            
            if result.debug_artifacts:
                self._save_debug(tool_name, result.debug_artifacts)
            
            # Handle quality gate re-run
            if tool_name == "quality_gate" and result.data and result.data.get("retry"):
                self._rerun_phase2()
        
        return self.state
    
    def _rerun_phase2(self):
        """Re-execute Phase 2 tools with adjusted parameters."""
        phase2_tools = [(n, m) for n, m in self.PIPELINE if m["phase"] == 2]
        for tool_name, meta in phase2_tools:
            result = self._execute_with_retry(tool_name, retries=1)
            self.history.append({"tool": f"{tool_name}_retry", "result": result})
```

### 4.3 Agent State

```python
# FILE: agent/state.py

@dataclass
class AgentState:
    # --- Phase 1: Scene Understanding ---
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
    scene_layout: dict = field(default_factory=dict)   # From VLM scene analysis
    scene_depth_map: np.ndarray | None = None          # Single depth map of full scene
    scene_depth_stats: dict = field(default_factory=dict)
    adaptive_params: dict = field(default_factory=dict)
    
    # --- Phase 2: Zone Discovery ---
    dwell_points: list = field(default_factory=list)
    zone_candidates_A: list = field(default_factory=list)
    zone_candidates_B: list = field(default_factory=list)
    zone_candidates_C: list = field(default_factory=list)
    fused_zones: list = field(default_factory=list)
    static_structures: list = field(default_factory=list)
    
    # --- Phase 3: Zone Enrichment ---
    zone_crops: dict = field(default_factory=dict)       # {zone_id: {"standard": b64, "wide": b64}}
    zone_depth_info: dict = field(default_factory=dict)  # {zone_id: {"avg_depth": ..., "size_estimate": ...}}
    zone_objects: dict = field(default_factory=dict)      # {zone_id: [objects from VLM]}
    zone_signage: dict = field(default_factory=dict)      # {zone_id: [text found]}
    zone_classifications: dict = field(default_factory=dict)
    zone_descriptions: dict = field(default_factory=dict)
    zone_registry: dict = field(default_factory=dict)     # Final merged registry
    
    # --- Phase 4: Analytics ---
    zone_analytics: dict = field(default_factory=dict)
    flow_analytics: dict = field(default_factory=dict)
    temporal_analytics: dict = field(default_factory=dict)
    spatial_analytics: dict = field(default_factory=dict)
    
    # --- Phase 5: Validation ---
    validation_metrics: dict = field(default_factory=dict)
    quality_passed: bool = False
    
    # --- Phase 6: Visualization ---
    visualization_plan: list = field(default_factory=list)
    
    # --- Meta ---
    video_id: str = ""
    video_duration_seconds: float = 0.0
    current_step: str = ""
    errors: list = field(default_factory=list)
```

---

### 4.4 PHASE 1 TOOLS

#### t03: `calibrate_from_person_height` (KEY CHANGE — no depth dependency)

```python
# FILE: agent/tools/phase1_calibrate.py

"""
CAMERA CALIBRATION FROM PERSON-HEIGHT REGRESSION

This is the primary calibration method. It uses ONLY tracking data
(no Replicate API call needed). It works because:

1. People are approximately 1.7m tall (±0.15m)
2. In a perspective camera, apparent height (pixels) decreases linearly
   with distance from camera
3. By measuring bbox heights at different y-positions in the image,
   we can fit a vanishing point model and estimate the ground plane

The math:
  pixel_height(y) = focal_length * real_height / distance(y)
  Since distance increases with y-position (for typical CCTV),
  we fit: pixel_height = a / (y - y_vanishing) + b

This gives us enough to compute a homography from image plane to
ground plane (BEV).

Enhancement (optional, Phase 1 tool t06):
  If depth_scene_analysis also runs, we can refine the homography
  using metric depth data. But the person-height method works standalone.
"""

import numpy as np
import cv2
from scipy.optimize import least_squares

AVERAGE_PERSON_HEIGHT_M = 1.7

@ToolRegistry.register("calibrate_from_person_height")
def calibrate_from_person_height(state, config):
    df = state.raw_tracks
    H_img, W_img = state.frame_shape[:2]
    
    # --- Step 1: Collect bbox height samples at various y positions ---
    # Use median bbox height per y-band to reduce noise
    # Only use high-quality detections (confidence > 0.5)
    good = df[(df["confidence"] > 0.5) & (df["bbox_h"] > 20)]
    
    # Bin by y-center position (20 bands across image height)
    n_bands = 20
    band_height = H_img / n_bands
    
    y_positions = []  # Median y-center per band
    px_heights = []   # Median bbox height per band
    
    for band in range(n_bands):
        y_lo = band * band_height
        y_hi = (band + 1) * band_height
        band_data = good[(good["y_center"] >= y_lo) & (good["y_center"] < y_hi)]
        
        if len(band_data) >= 5:  # Need enough samples
            y_positions.append(band_data["y_center"].median())
            px_heights.append(band_data["bbox_h"].median())
    
    y_positions = np.array(y_positions)
    px_heights = np.array(px_heights)
    
    if len(y_positions) < 4:
        # Insufficient data — fall back to simple scaling
        return _fallback_simple_scaling(state, config)
    
    # --- Step 2: Fit perspective model ---
    # Model: px_height = K / (y - y_vanishing)
    # where K = focal_length * real_height, y_vanishing = vanishing point y
    # 
    # This is the key insight: in a pinhole camera looking at a flat ground,
    # objects at the horizon (vanishing point) have zero pixel height.
    # The relationship between y-position and pixel height reveals the
    # ground plane geometry.
    
    def residual(params):
        K, y_vp = params
        predicted = K / (y_positions - y_vp + 1e-6)
        return predicted - px_heights
    
    # Initial guess: vanishing point above image, K from mean
    y_vp_init = -H_img * 0.5  # Above frame
    K_init = np.mean(px_heights * (y_positions - y_vp_init))
    
    result = least_squares(residual, [K_init, y_vp_init],
                          bounds=([0, -H_img*5], [K_init*10, H_img*0.3]))
    K_fit, y_vp_fit = result.x
    
    # --- Step 3: Estimate focal length ---
    # K = focal_length * person_height_meters
    focal_length_px = K_fit / AVERAGE_PERSON_HEIGHT_M
    
    # --- Step 4: Compute ground plane homography ---
    # For a camera looking at a flat ground plane:
    # We define 4 reference points at known positions in the image
    # and map them to ground-plane coordinates using the fitted model.
    
    # Ground distance at y-position: d(y) = K / px_height(y) * person_height
    # But px_height(y) = K / (y - y_vp), so d(y) = (y - y_vp) * person_height
    # This is a linear mapping! Perfect for homography.
    
    # Select 4 source points spanning the image
    y_lo = max(y_positions.min(), H_img * 0.3)  # Don't use top of image
    y_hi = min(y_positions.max(), H_img * 0.95)
    
    src_points = np.array([
        [W_img * 0.2, y_lo],
        [W_img * 0.8, y_lo],
        [W_img * 0.8, y_hi],
        [W_img * 0.2, y_hi],
    ], dtype=np.float32)
    
    # Compute BEV coordinates for each source point
    bev_resolution = config.bev_resolution  # meters per BEV pixel (e.g., 0.05)
    
    dst_points = []
    for sx, sy in src_points:
        # Distance from camera (along ground) at this y position
        ground_dist = (sy - y_vp_fit) * AVERAGE_PERSON_HEIGHT_M / focal_length_px * focal_length_px
        # Simplified: ground_dist proportional to (y - y_vp)
        ground_dist_m = K_fit / focal_length_px  # Base distance scale
        dist_at_y = abs(sy - y_vp_fit) * AVERAGE_PERSON_HEIGHT_M
        
        # Horizontal offset in meters
        x_offset_m = (sx - W_img/2) * dist_at_y / focal_length_px
        
        # BEV pixel coordinates
        bev_x = (x_offset_m / bev_resolution) + 500  # Offset so BEV doesn't go negative
        bev_y = (dist_at_y / bev_resolution)
        
        dst_points.append([bev_x, bev_y])
    
    dst_points = np.array(dst_points, dtype=np.float32)
    
    # Compute homography
    homography, _ = cv2.findHomography(src_points, dst_points)
    
    # Determine BEV image size
    corners = np.array([[0,0],[W_img,0],[W_img,H_img],[0,H_img]], dtype=np.float32)
    corners_h = np.hstack([corners, np.ones((4,1))]).T
    bev_corners = (homography @ corners_h).T
    bev_corners = bev_corners[:,:2] / bev_corners[:,2:3]
    
    bev_w = int(bev_corners[:,0].max() - bev_corners[:,0].min()) + 1
    bev_h = int(bev_corners[:,1].max() - bev_corners[:,1].min()) + 1
    bev_w = min(max(bev_w, 200), 2500)
    bev_h = min(max(bev_h, 200), 2500)
    
    state.homography_matrix = homography
    state.bev_scale = bev_resolution
    state.bev_size = (bev_w, bev_h)
    state.calibration_method = "person_height"
    
    # --- Step 5: Transform all tracks to BEV ---
    pts = df[["x_center", "y_center"]].values.astype(np.float32)
    pts_h = np.hstack([pts, np.ones((len(pts), 1))])
    bev = (homography @ pts_h.T).T
    bev = bev[:,:2] / bev[:,2:3]
    
    df["bev_x"] = bev[:, 0]
    df["bev_y"] = bev[:, 1]
    df["bev_x_meters"] = bev[:, 0] * bev_resolution
    df["bev_y_meters"] = bev[:, 1] * bev_resolution
    
    # Recompute speed in meters/second
    df["bev_dx"] = df.groupby("track_id")["bev_x_meters"].diff().fillna(0)
    df["bev_dy"] = df.groupby("track_id")["bev_y_meters"].diff().fillna(0)
    df["speed_m_s"] = np.sqrt(df["bev_dx"]**2 + df["bev_dy"]**2) / df["dt"].clip(lower=1e-6)
    
    # --- Step 6: Validation ---
    # In BEV, all people should have roughly similar "footprint" sizes
    # Check variance of bbox_h * bev_scale is low
    fit_residual = float(np.mean(result.fun**2)**0.5)
    
    # Warp reference frame for debug
    bev_image = cv2.warpPerspective(state.reference_frame, homography, (bev_w, bev_h))
    
    return ToolResult(
        success=True,
        data={
            "focal_length_px": float(focal_length_px),
            "vanishing_point_y": float(y_vp_fit),
            "bev_size": (bev_w, bev_h),
            "bev_resolution": bev_resolution,
            "fit_residual": fit_residual,
            "n_height_samples": len(y_positions),
        },
        message=f"Calibrated BEV {bev_w}x{bev_h} @ {bev_resolution}m/px "
                f"from {len(y_positions)} height bands, f={focal_length_px:.0f}px",
        debug_artifacts={
            "bev_reference_frame": bev_image,
            "height_regression": _plot_height_regression(
                y_positions, px_heights, K_fit, y_vp_fit
            ),
            "bev_track_scatter": _plot_bev_tracks(df, bev_w, bev_h),
        }
    )
```

#### t06: `depth_scene_analysis` (Depth as knowledge tool, NOT tracker)

```python
# FILE: agent/tools/phase1_depth.py

"""
DEPTH AS SCENE KNOWLEDGE TOOL

Runs Depth Pro (via Replicate) on the reference frame ONCE.
This is NOT per-frame depth. It's a single API call to understand
the spatial structure of the scene.

Uses:
1. Enhance BEV calibration (if person-height regression is coarse)
2. Provide depth context for VLM prompts in Phase 3
   ("this zone is ~8m from camera, the area spans ~3m in depth")
3. Identify depth discontinuities (walls, steps, level changes)
4. Enable 3D scene visualization in dashboard
5. Estimate physical sizes of zones for analytics

This tool is OPTIONAL. The pipeline works without it
(using person-height calibration alone). But depth adds significant
value to zone enrichment and visualization.
"""

@ToolRegistry.register("depth_scene_analysis")
def depth_scene_analysis(state, config):
    if not config.replicate_api_token:
        return ToolResult(
            success=True,
            message="Replicate API not configured, skipping depth. "
                    "Pipeline uses person-height calibration only.",
            data={"depth_available": False}
        )
    
    import replicate
    
    # Encode reference frame
    frame = state.reference_frame
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    
    # Call Depth Pro via Replicate (1 API call)
    output = replicate.run(
        "ibrahimpenekli/depth-pro",
        input={"image": buf}
    )
    
    depth_map = _download_and_parse_depth(output)
    focal_length = _extract_focal_length(output)
    
    state.scene_depth_map = depth_map
    state.scene_depth_stats = {
        "min_depth": float(depth_map[depth_map > 0.1].min()) if (depth_map > 0.1).any() else 0,
        "max_depth": float(depth_map.max()),
        "median_depth": float(np.median(depth_map[depth_map > 0.1])),
        "focal_length_from_depth": focal_length,
    }
    
    # Optionally refine BEV calibration using depth
    if focal_length and state.calibration_method == "person_height":
        _refine_calibration_with_depth(state, depth_map, focal_length)
    
    return ToolResult(
        success=True,
        data={
            "depth_available": True,
            "depth_range": f"{state.scene_depth_stats['min_depth']:.1f}-"
                          f"{state.scene_depth_stats['max_depth']:.1f}m",
        },
        message=f"Scene depth: {state.scene_depth_stats['min_depth']:.1f}-"
                f"{state.scene_depth_stats['max_depth']:.1f}m",
        debug_artifacts={
            "depth_map_colorized": _colorize_depth_map(depth_map),
            "depth_histogram": _plot_depth_histogram(depth_map),
        }
    )
```

---

### 4.5 PHASE 2 TOOLS (Zone Discovery)

Tools t07-t11 are identical to v3 spec (they all operate in BEV meters).
See the ensemble fusion approach with 3 strategies + voting.

**Key addition: t12 `vlm_detect_structures`**

```python
# FILE: agent/tools/phase2_structures.py

"""
Use VLM to detect static structures visible in the scene.
These are zones that exist REGARDLESS of whether people are there.

Examples: shop counters, table clusters, doorways, barriers, kiosks, ATMs.

This tool asks the VLM to identify and roughly locate structural elements
in the reference frame. These become "structure-based zone candidates"
that are merged with movement-based zones in Phase 3.

Why this matters:
- A shop that had zero visitors during the video still needs a zone
- Corridors are defined by walls/barriers, not just movement
- Table clusters define seating areas even when empty
"""

VLM_STRUCTURES_PROMPT = """
Analyze this CCTV image and identify all FIXED STRUCTURAL ELEMENTS that 
define functional areas. For each element, provide its approximate 
location as a bounding box in normalized coordinates [0-1].

Look for:
- Service counters, registers, cash registers
- Table clusters (dining tables, café tables)
- Chairs, benches, seating arrangements  
- Doorways, entrances, exits, gates
- Barriers, railings, pillars, walls
- Kiosks, vending machines, ATMs
- Menu boards, signage displays
- Shelving, display cases, merchandise areas
- Planters, decorative elements that create boundaries

For each structure found, provide:
- type: what it is
- bbox: [x_min, y_min, x_max, y_max] in normalized 0-1 coordinates
- zone_implication: what kind of zone this structure suggests
  (e.g., "counter" → "restaurant", "tables" → "seating_area")
- confidence: how certain you are [0-1]

Respond ONLY in JSON:
{
    "structures": [
        {
            "type": "service_counter",
            "bbox": [0.2, 0.15, 0.35, 0.35],
            "zone_implication": "restaurant",
            "confidence": 0.9,
            "description": "Long counter with cash register visible"
        }
    ]
}
"""
```

---

### 4.6 PHASE 3 TOOLS: VLM Toolkit (THE KEY CHANGE)

Phase 3 is completely restructured. Instead of one VLM "verification" call,
there are **5 specialized VLM tools**, each with a distinct prompt and purpose.
They run sequentially per zone, building up a rich understanding.

#### t14: `depth_zone_analysis` (Depth on CROPS, not tracker)

```python
# FILE: agent/tools/phase3_depth_zones.py

"""
Run depth estimation on each zone CROP to understand physical dimensions.

This is the second use of depth (first was t06 on the full scene).
Here we get per-zone spatial knowledge:
- Average depth (distance from camera)
- Depth range within zone (flat floor vs. stepped/elevated)
- Estimated physical width and depth in meters

This information is INJECTED INTO subsequent VLM prompts to help the
VLM make better classifications. E.g.:
  "This zone is approximately 4m × 3m at 7m from camera"
  helps VLM distinguish a small kiosk from a large restaurant.

If Replicate API is not available, this tool is skipped gracefully.
Zone dimensions are estimated from BEV polygon area instead.
"""

@ToolRegistry.register("depth_zone_analysis")
def depth_zone_analysis(state, config):
    if state.scene_depth_map is None:
        # No depth available — estimate from BEV polygon area
        for zone_id, zone in state.zone_registry_draft.items():
            area_m2 = zone.get("area_m2", 0)
            side = area_m2 ** 0.5
            state.zone_depth_info[zone_id] = {
                "avg_depth_m": None,
                "width_estimate_m": side,
                "depth_estimate_m": side,
                "source": "bev_polygon"
            }
        return ToolResult(success=True, message="Estimated sizes from BEV (no depth)")
    
    depth_map = state.scene_depth_map
    
    for zone_id, crop_data in state.zone_crops.items():
        zone = state.fused_zones_dict[zone_id]
        
        # Get zone bbox in pixel coordinates
        bbox = zone["bbox_pixel"]  # [x1, y1, x2, y2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        
        # Extract depth within zone bbox
        zone_depth = depth_map[y1:y2, x1:x2]
        valid = zone_depth[zone_depth > 0.1]
        
        if len(valid) > 10:
            avg_depth = float(np.median(valid))
            depth_range = float(valid.max() - valid.min())
            
            # Estimate physical size using pinhole model
            focal = state.scene_depth_stats.get("focal_length_from_depth") or \
                    (state.frame_shape[1] * 1.15)
            width_m = (x2 - x1) * avg_depth / focal
            height_m = (y2 - y1) * avg_depth / focal
        else:
            avg_depth = None
            depth_range = 0
            area = zone.get("area_m2", 4)
            width_m = area ** 0.5
            height_m = width_m
        
        state.zone_depth_info[zone_id] = {
            "avg_depth_m": avg_depth,
            "depth_range_m": depth_range,
            "width_estimate_m": round(width_m, 1),
            "depth_estimate_m": round(height_m, 1),
            "source": "depth_pro" if avg_depth else "bev_polygon"
        }
    
    return ToolResult(
        success=True,
        data={"zones_with_depth": sum(1 for v in state.zone_depth_info.values() 
                                       if v["avg_depth_m"] is not None)},
        debug_artifacts={
            "zone_depth_summary": _plot_zone_depths(state.zone_depth_info)
        }
    )
```

#### t15: `vlm_object_inventory` (VLM as object detector)

```python
# FILE: agent/tools/phase3_vlm_objects.py

"""
VLM TOOL: Object Inventory

For each zone crop, ask the VLM to identify EVERY visible object.
This is not classification — it's detection/enumeration.

The VLM acts as a flexible object detector that can find things
traditional detectors can't: menu boards, cash registers, napkin dispensers,
coffee machines, specific chair types, branded signage, etc.

The object list is used downstream by:
- vlm_zone_classifier: objects inform zone type
- vlm_zone_describer: objects appear in description
- Analytics: object presence becomes a zone feature
"""

VLM_OBJECT_INVENTORY_PROMPT = """
You are analyzing a cropped region from a CCTV camera.
{depth_context}

List EVERY distinct object you can identify in this image.
Be specific and thorough. Include:
- Furniture: tables, chairs, benches, stools, counters, shelves
- Equipment: cash registers, screens/monitors, coffee machines, ovens
- Signage: menu boards, price displays, business name signs, logos
- Infrastructure: doors, windows, barriers, railings, pillars, lights
- Containers: trash bins, displays, refrigerators, shelving units
- Decorative: plants, posters, artwork
- People-related: queuing barriers, trays, condiment stations

For each object provide:
- name: specific name (not just "furniture" but "round dining table")
- count: how many visible (exact or approximate)
- location: where in the crop ("left", "center", "right", "background")
- condition/state: relevant details ("occupied", "empty", "lit up")

Respond ONLY in JSON:
{{
    "objects": [
        {{
            "name": "round dining table",
            "count": 4,
            "location": "center",
            "state": "2 occupied, 2 empty"
        }},
        {{
            "name": "menu board with prices",
            "count": 1,
            "location": "top-left, above counter",
            "state": "illuminated"
        }}
    ],
    "total_object_types": <int>,
    "scene_density": "sparse" | "moderate" | "dense"
}}
"""

@ToolRegistry.register("vlm_object_inventory")
def vlm_object_inventory(state, config):
    vlm = OpenRouterVLM(config.openrouter_api_key, config.vlm_primary_model)
    
    for zone_id, crops in state.zone_crops.items():
        # Build depth context string if available
        depth_info = state.zone_depth_info.get(zone_id, {})
        if depth_info.get("avg_depth_m"):
            depth_context = (
                f"Spatial context: This area is approximately "
                f"{depth_info['width_estimate_m']}m wide × "
                f"{depth_info['depth_estimate_m']}m deep, "
                f"at {depth_info['avg_depth_m']:.0f}m from the camera."
            )
        else:
            depth_context = ""
        
        prompt = VLM_OBJECT_INVENTORY_PROMPT.format(depth_context=depth_context)
        
        try:
            result = await vlm.query_with_image(crops["standard"], prompt)
            state.zone_objects[zone_id] = result.get("objects", [])
        except Exception as e:
            logger.warning(f"Object inventory failed for {zone_id}: {e}")
            state.zone_objects[zone_id] = []
    
    total_objects = sum(len(objs) for objs in state.zone_objects.values())
    
    return ToolResult(
        success=True,
        data={"total_object_types_found": total_objects},
        message=f"Found {total_objects} object types across {len(state.zone_objects)} zones",
        debug_artifacts={
            "object_summary": _create_object_summary_table(state.zone_objects)
        }
    )
```

#### t16: `vlm_signage_reader`

```python
# FILE: agent/tools/phase3_vlm_signage.py

"""
VLM TOOL: Signage Reader

Extract any readable text from zone crops: business names, menu items,
prices, warnings, directions. This is used to name zones accurately.

This is separated from object inventory because:
1. It needs a different prompt optimized for OCR/text extraction
2. Text extraction often needs the WIDE crop (signage above the zone)
3. It directly produces the zone's business_name
"""

VLM_SIGNAGE_PROMPT = """
Examine this image carefully for ANY readable text, signage, logos, or writing.

Look for:
- Business names (restaurant names, shop names, brand names)
- Menu boards and price lists
- Directional signs (Exit, Entrance, Restrooms, etc.)
- Warning or information signs
- Logos that identify a brand even without text
- Numbers (addresses, phone numbers, prices)
- Any text on screens, monitors, or digital displays

For each text element found:
- text: the exact text as written (preserve capitalization)
- type: "business_name" | "menu" | "directional" | "info" | "brand_logo" | "price" | "other"
- confidence: how confident you are in the reading [0-1]
- location: where in the image

If NO text is visible, respond with an empty list.

Respond ONLY in JSON:
{{
    "text_elements": [
        {{
            "text": "SUBWAY",
            "type": "business_name",
            "confidence": 0.95,
            "location": "top-center, green background sign"
        }}
    ],
    "primary_business_name": "Subway" or null
}}
"""
```

#### t17: `vlm_zone_classifier`

```python
# FILE: agent/tools/phase3_vlm_classify.py

"""
VLM TOOL: Zone Classifier

Classifies each zone using ALL available context:
- The zone crop image
- Objects found by vlm_object_inventory
- Signage found by vlm_signage_reader
- Behavioral data (dwell time, visit count, flow patterns)
- Depth/size information
- Scene layout context from vlm_scene_layout

This is the most sophisticated VLM call because it synthesizes
multiple data sources into a classification decision.
"""

VLM_CLASSIFY_PROMPT = """
Classify this zone from a CCTV camera in a {scene_type} environment.

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
- Estimated size: {width}m × {depth}m
- Distance from camera: {distance}m
- Area: {area}m²

Given ALL this evidence, classify the zone:

Respond ONLY in JSON:
{{
    "zone_type": "<one of: restaurant, fast_food, cafe, seating_area,
                  corridor, entrance, exit, kiosk, atm, restroom_area,
                  shop, service_counter, waiting_area, food_prep_area,
                  information_desk, open_space, unknown>",
    "confidence": <0.0-1.0>,
    "reasoning": "2-3 sentences explaining why this classification",
    "alternative_type": "<second most likely type>" or null,
    "alternative_confidence": <0.0-1.0> or null
}}
"""
```

#### t18: `vlm_zone_describer`

```python
# FILE: agent/tools/phase3_vlm_describe.py

"""
VLM TOOL: Zone Description Generator

Generates a rich, human-readable description for each zone.
Uses ALL data collected so far: objects, signage, classification,
behavioral patterns, spatial dimensions.

The description appears in the dashboard's zone detail panel.
"""

VLM_DESCRIBE_PROMPT = """
Write a 3-5 sentence description of this zone for a retail analytics report.

Zone: "{business_name}" (classified as: {zone_type})
Objects: {objects_summary}
Signage: {signage_summary}
Size: approximately {width}m × {depth}m
Behavioral: {avg_dwell}s avg dwell, {visits}/hr, peak at {peak_hour}:00

Write a professional but concise description that:
1. States what the zone IS (type, business)
2. Describes its physical characteristics (size, key objects)
3. Summarizes its usage patterns (busy times, dwell behavior)
4. Notes anything distinctive

Respond with ONLY the description text, no JSON.
"""
```

---

### 4.7 PHASE 3 MERGE: Combining everything

```python
# FILE: agent/tools/phase3_merge.py

"""
t19: merge_zone_registry

Combines ALL data into the final ZoneRegistry:
- Fused zone polygons (from Phase 2 ensemble)
- Static structures (from Phase 2 VLM)
- Depth info (from t14)
- Object inventory (from t15)
- Signage (from t16)
- Classification (from t17)
- Description (from t18)

Also handles:
- Merging movement-based zones with structure-based zones
  (if a structure overlaps with a movement zone, merge them)
- De-duplicating zone names (two zones can't both be "Subway")
- Assigning final zone_ids: "zone_001", "zone_002", etc.
- Computing zone bboxes in both pixel and BEV coordinates
- Inverse-projecting BEV polygons back to pixel space for rendering
"""

@ToolRegistry.register("merge_zone_registry")
def merge_zone_registry(state, config):
    registry = {}
    
    for zone in state.fused_zones:
        zid = zone["zone_id"]
        
        # Inverse-project BEV polygon back to pixel coordinates
        polygon_bev = np.array(zone["polygon_bev"], dtype=np.float32)
        # Use inverse homography for BEV→pixel
        H_inv = np.linalg.inv(state.homography_matrix)
        polygon_pixel = _project_bev_to_pixel(polygon_bev, H_inv, state.bev_scale)
        
        # Gather all VLM data
        objects = state.zone_objects.get(zid, [])
        signage = state.zone_signage.get(zid, {})
        classification = state.zone_classifications.get(zid, {})
        description = state.zone_descriptions.get(zid, "")
        depth_info = state.zone_depth_info.get(zid, {})
        
        # Determine business name priority:
        # 1. Signage reader found a name → use it
        # 2. VLM classifier suggested a name → use it
        # 3. Generate descriptive name: "{type} {letter}"
        business_name = (
            signage.get("primary_business_name") or
            classification.get("suggested_name") or
            _generate_zone_name(classification.get("zone_type", "unknown"), zid)
        )
        
        registry[zid] = {
            "zone_id": zid,
            "business_name": business_name,
            "zone_type": classification.get("zone_type", "unknown"),
            "vlm_confidence": classification.get("confidence", 0.0),
            "description": description,
            "polygon_bev": zone["polygon_bev"],
            "polygon_pixel": polygon_pixel.tolist(),
            "centroid_bev": zone["centroid_bev"],
            "area_m2": zone.get("area_m2", 0),
            "depth_info": depth_info,
            "objects": objects,
            "signage": signage,
            "strategy_agreement": zone.get("strategy_agreement", 0),
            "contributing_strategies": zone.get("contributing_strategies", []),
        }
    
    # Merge static structures that DON'T overlap with movement zones
    for structure in state.static_structures:
        # Check if any existing zone overlaps with this structure
        overlaps = _find_overlapping_zone(structure, registry)
        if overlaps:
            # Merge structure info into existing zone
            registry[overlaps]["structures_detected"] = True
        else:
            # Create new zone from structure alone
            new_id = f"zone_{len(registry)+1:03d}"
            registry[new_id] = _create_zone_from_structure(new_id, structure)
    
    # De-duplicate names
    _deduplicate_names(registry)
    
    state.zone_registry = registry
    
    return ToolResult(
        success=True,
        data={"total_zones": len(registry)},
        message=f"Final registry: {len(registry)} zones",
        debug_artifacts={
            "zone_registry_table": _create_registry_table(registry),
            "zone_map_labeled": _plot_labeled_zones(
                state.reference_frame, registry, state.homography_matrix
            ),
        }
    )
```

---

### 4.8 PHASE 4: Analytics (t20-t23)

Same as v3 spec. Four tools computing zone, flow, temporal, and spatial analytics.
All operate in BEV meters. All produce debug visualizations.

### 4.9 PHASE 5: Validation (t24-t25)

Same as v3 spec. Silhouette score, coverage %, temporal stability, VLM agreement.
Quality gate can trigger Phase 2 re-run with adjusted parameters.

### 4.10 PHASE 6: Visualization & Export (t26-t29)

#### t26: `plan_visualizations` (Agentic)

```python
VIZ_PLANNER_PROMPT = """
You are a data visualization expert planning a dashboard for retail analytics.

SCENE: {scene_type}
ZONES: {n_zones} ({zone_types_summary})
DATA: {n_tracks} visitors, {duration}, depth {'available' if depth else 'not available'}
HIGHLIGHTS: {key_findings}

Available visualization types:
1. zone_map_perspective — zones overlaid on camera image
2. zone_map_bev — bird's eye view zone map
3. heatmap_perspective — density heatmap on camera view
4. heatmap_bev — density heatmap on BEV
5. sankey_flow — zone-to-zone transition diagram (skip if < 3 zones)
6. temporal_heatmap — zone × hour occupancy matrix
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
        {{"type": "...", "priority": 1, "reason": "..."}},
        ...
    ],
    "highlighted_zones": ["zone_001", ...],
    "kpi_metrics": ["total_visitors", "avg_dwell", ...],
    "theme": "warm" | "cool" | "neutral"
}}
"""
```

---

## 5. MODULE C: DASHBOARD

### 5.1 Design System

```css
/* Dark Observatory theme */
:root {
  --bg-primary:     #0a0a0f;
  --bg-card:        #12121a;
  --bg-hover:       #1a1a26;
  --border:         #1e1e2e;
  --text-primary:   #e8e8ec;
  --text-secondary: #6e6e82;
  --accent-cyan:    #00d4ff;
  --accent-amber:   #ff9500;
  --accent-green:   #00ff88;
  --accent-red:     #ff3366;
  
  --zone-restaurant: #ff6b35;
  --zone-cafe:       #ffc233;
  --zone-seating:    #339dff;
  --zone-corridor:   #4a4a5e;
  --zone-entrance:   #00ff88;
  --zone-shop:       #b366ff;
  --zone-unknown:    #3a3a4e;
}
/* Typography: JetBrains Mono (data), DM Sans (body) */
```

### 5.2 Component Tree

See v3 spec Section 5.2 — identical component structure.
React + Recharts + D3 + Three.js + Framer Motion + Tailwind.

---

## 6. DATABASE SCHEMA

```sql
-- FILE: tracker/schema.sql
-- Module A populates: videos, detections, tracks, keyframes
-- Module B populates: zones, zone_analytics, zone_transitions, pipeline_runs
-- NO depth_maps table — depth is transient in Module B, not stored in DB

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    fps REAL NOT NULL,
    total_frames INTEGER NOT NULL,
    width INTEGER NOT NULL, height INTEGER NOT NULL,
    duration_seconds REAL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    track_id INTEGER NOT NULL,
    x_center REAL NOT NULL, y_center REAL NOT NULL,
    bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL,
    bbox_w REAL, bbox_h REAL,
    confidence REAL,
    object_class TEXT DEFAULT 'person'
);
CREATE INDEX IF NOT EXISTS idx_det_vt ON detections(video_id, track_id);
CREATE INDEX IF NOT EXISTS idx_det_vf ON detections(video_id, frame_idx);

CREATE TABLE IF NOT EXISTS tracks (
    video_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    first_frame INTEGER, last_frame INTEGER,
    first_timestamp REAL, last_timestamp REAL,
    duration_seconds REAL, duration_frames INTEGER,
    num_detections INTEGER,
    avg_confidence REAL,
    path_length_pixels REAL,
    avg_speed_px_per_sec REAL,
    quality_score REAL DEFAULT 0.5,
    gender TEXT, age_group TEXT,
    PRIMARY KEY (video_id, track_id)
);

CREATE TABLE IF NOT EXISTS keyframes (
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    frame_data BLOB NOT NULL,
    PRIMARY KEY (video_id, frame_idx)
);

-- Populated by Module B
CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    business_name TEXT, zone_type TEXT, description TEXT,
    vlm_confidence REAL,
    polygon_bev_json TEXT, polygon_pixel_json TEXT,
    centroid_bev_x REAL, centroid_bev_y REAL,
    area_m2 REAL,
    objects_json TEXT,        -- VLM object inventory
    signage_json TEXT,        -- VLM signage reader output
    depth_info_json TEXT,     -- Depth analysis results
    strategy_agreement INTEGER,
    contributing_strategies TEXT
);

CREATE TABLE IF NOT EXISTS zone_analytics (
    zone_id TEXT PRIMARY KEY,
    total_visits INTEGER, unique_visitors INTEGER,
    avg_dwell_seconds REAL, median_dwell_seconds REAL, p95_dwell_seconds REAL,
    peak_hour INTEGER,
    hourly_visits_json TEXT,
    gender_distribution_json TEXT,
    avg_occupancy REAL, max_occupancy INTEGER,
    return_rate REAL,
    density_people_per_m2_hr REAL
);

CREATE TABLE IF NOT EXISTS zone_transitions (
    from_zone TEXT, to_zone TEXT,
    count INTEGER, avg_travel_seconds REAL, probability REAL,
    PRIMARY KEY (from_zone, to_zone)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    started_at TIMESTAMP, completed_at TIMESTAMP,
    status TEXT, config_json TEXT,
    validation_metrics_json TEXT,
    n_zones_discovered INTEGER,
    calibration_method TEXT
);
```

---

## 7. EXTERNAL API INTEGRATION

| Service | When Called | How Many Calls | Cost per Run |
|---------|-----------|----------------|--------------|
| **Replicate (Depth Pro)** | t06: scene depth (1 call), t14: zone crops (~12 calls) | ~13 total | ~$0.13 |
| **OpenRouter (Qwen3.5-Plus)** | t05: scene layout (1), t12: structures (1), t15: objects (~12), t16: signage (~12), t17: classify (~12), t18: describe (~12), t26: viz plan (1) | ~51 total | ~$0.50-2.00 |
| **OpenRouter (Qwen3.5-Flash)** | VLM retries, wide-crop fallbacks | ~5-10 | ~$0.05-0.10 |
| **Total** | | ~70 API calls | **~$0.70-2.25** |

OpenRouter client: see v3 spec Section 7.1.

---

## 8. CONFIGURATION

```python
# FILE: agent/config.py

from pydantic_settings import BaseSettings
from pathlib import Path

class PipelineConfig(BaseSettings):
    # API Keys
    openrouter_api_key: str
    replicate_api_token: str = ""  # Optional — pipeline works without it
    
    # Paths
    db_path: Path = Path("data/retailvision.db")
    video_id: str = ""
    output_dir: Path = Path("output")
    
    # Calibration
    bev_resolution: float = 0.05  # meters per BEV pixel
    person_height_m: float = 1.7
    
    # VLM
    vlm_primary_model: str = "qwen/qwen3.5-plus-02-15"
    vlm_fallback_model: str = "qwen/qwen3.5-flash-02-23"
    vlm_temperature: float = 0.2
    vlm_max_retries: int = 3
    vlm_confidence_threshold: float = 0.5
    vlm_crop_margin_pct: float = 0.20
    vlm_wide_margin_pct: float = 0.40
    
    # Quality
    quality_threshold: float = 0.40
    track_quality_threshold: float = 0.3
    
    # Tracker (used by Module A)
    yolo_model: str = "yolo26m.pt"
    tracker_yaml: str = "tracker/botsort_retail.yaml"
    detect_classes: list[int] = [0]
    detection_conf: float = 0.25
    detection_iou: float = 0.5
    imgsz: int = 1280
    keyframe_interval: int = 150
    
    class Config:
        env_file = ".env"
```

---

## 9. TESTING & VALIDATION

### 9.1 Test Structure

```
tests/
├── conftest.py                  # Shared fixtures, mock VLM
├── fixtures/
│   ├── sample_video_10s.mp4
│   ├── sample_db.sqlite
│   ├── mock_vlm_responses.json  # Canned VLM outputs for all 5 tools
│   └── synthetic_tracks.csv
├── unit/
│   ├── test_database.py
│   ├── test_calibration.py      # Person-height regression
│   ├── test_dwell_detection.py
│   ├── test_strategy_a.py       # Dwell clustering
│   ├── test_strategy_b.py       # Occupancy grid
│   ├── test_strategy_c.py       # Trajectory graph
│   ├── test_fusion.py           # Ensemble voting
│   ├── test_validation.py       # Quality metrics
│   ├── test_vlm_client.py       # OpenRouter mocked
│   └── test_vlm_prompts.py      # Prompt formatting
├── integration/
│   ├── test_tracker_pipeline.py
│   ├── test_agent_pipeline.py
│   └── test_full_e2e.py
└── visual/
    ├── test_debug_plots.py
    └── test_report_schema.py
```

### 9.2 Key Test: Calibration Without Depth

```python
class TestPersonHeightCalibration:
    def test_typical_cctv_view(self):
        """Simulated CCTV: people appear larger at bottom, smaller at top."""
        # Generate fake tracks where bbox_h decreases with y_center
        df = make_tracks_with_perspective(n_tracks=100, image_h=1080)
        state = mock_state(raw_tracks=df)
        result = calibrate_from_person_height(state, mock_config())
        
        assert result.success
        assert state.homography_matrix is not None
        assert state.bev_size[0] > 100
        assert state.bev_size[1] > 100
    
    def test_insufficient_tracks(self):
        """Few tracks should trigger fallback, not crash."""
        df = make_tracks_with_perspective(n_tracks=3, image_h=1080)
        state = mock_state(raw_tracks=df)
        result = calibrate_from_person_height(state, mock_config())
        assert result.success  # Fallback works
    
    def test_bev_speed_is_reasonable(self):
        """After BEV transform, walking speed should be ~1.2 m/s."""
        df = make_walking_tracks(speed_px_s=50, image_h=1080)
        state = mock_state(raw_tracks=df)
        calibrate_from_person_height(state, mock_config())
        median_speed = state.raw_tracks["speed_m_s"].median()
        assert 0.5 < median_speed < 3.0  # Reasonable walking speed
```

### 9.3 Synthetic Data Generator

```python
# FILE: scripts/generate_synthetic.py

def generate_synthetic_dataset(
    db_path="data/synthetic.db",
    n_tracks=500, duration_min=60, fps=30.0,
    W=1920, H=1080, seed=42
):
    """
    Generate realistic CCTV tracking data with known ground truth zones.
    
    Ground truth zones:
    - Subway (fast_food, top-left, high dwell)
    - Pizza Hut (fast_food, top-center, medium dwell)
    - Starbucks (cafe, top-right, high dwell)
    - Seating Area (seating, center, highest dwell)
    - Main Corridor (corridor, horizontal band, low dwell)
    - Entrance (entrance, left edge, zero dwell)
    
    Tracks: each enters from entrance/edge, visits 1-4 zones with
    realistic dwell times, transits through corridor, exits.
    
    Includes perspective effect: bbox_h decreases with y position.
    """
    pass  # Full implementation follows standard simulation pattern
```

---

## 10. FILE STRUCTURE

```
retailvision/
├── README.md
├── pyproject.toml
├── .env.example
├── Makefile
│
├── tracker/                         # MODULE A (zero API deps)
│   ├── __init__.py
│   ├── detector.py                  # YOLOv26 + BoTSORT
│   ├── database.py                  # SQLite wrapper
│   ├── schema.sql
│   ├── config.py
│   └── botsort_retail.yaml
│
├── agent/                           # MODULE B (API deps: OpenRouter, Replicate)
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── config.py
│   ├── models.py
│   ├── state.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── phase1_ingest.py         # t01-t02
│   │   ├── phase1_calibrate.py      # t03: person-height BEV
│   │   ├── phase1_scene.py          # t04-t05: classify + VLM layout
│   │   ├── phase1_depth.py          # t06: scene depth (Replicate)
│   │   ├── phase2_dwell.py          # t07
│   │   ├── phase2_strategy_a.py     # t08: dwell clustering
│   │   ├── phase2_strategy_b.py     # t09: occupancy grid
│   │   ├── phase2_strategy_c.py     # t10: trajectory graph
│   │   ├── phase2_fusion.py         # t11: ensemble voting
│   │   ├── phase2_structures.py     # t12: VLM static structures
│   │   ├── phase3_crop.py           # t13
│   │   ├── phase3_depth_zones.py    # t14: depth on crops (Replicate)
│   │   ├── phase3_vlm_objects.py    # t15: VLM object inventory
│   │   ├── phase3_vlm_signage.py    # t16: VLM signage reader
│   │   ├── phase3_vlm_classify.py   # t17: VLM zone classifier
│   │   ├── phase3_vlm_describe.py   # t18: VLM zone describer
│   │   ├── phase3_merge.py          # t19: merge zone registry
│   │   ├── phase4_analytics.py      # t20-t23
│   │   ├── phase5_validate.py       # t24-t25
│   │   └── phase6_visualize.py      # t26-t29
│   ├── vlm/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py
│   │   ├── prompts.py               # ALL prompt templates
│   │   └── replicate_client.py
│   └── viz/
│       ├── __init__.py
│       ├── bev_renderer.py
│       ├── perspective_renderer.py
│       ├── heatmap.py
│       ├── graph_viz.py
│       └── debug_panels.py
│
├── dashboard/                       # MODULE C
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/                         # (See v3 Section 5.2 for full tree)
│
├── scripts/
│   ├── run_tracker.py
│   ├── run_pipeline.py
│   ├── run_dashboard.py
│   ├── generate_synthetic.py
│   └── demo_e2e.py
│
├── tests/                           # (See Section 9.1)
├── data/                            # (gitignored)
└── output/                          # (gitignored)
    ├── report.json
    ├── 3d_scene.json
    ├── zones/
    └── debug/
```

---

## 11. IMPLEMENTATION ORDER (20 Days)

```
SPRINT 1: Tracker (Days 1-3)
  Day 1: Project scaffold, SQLite schema, database.py
  Day 2: RetailTracker (YOLOv26 + BoTSORT), run_tracker.py
  Day 3: Track quality scoring, generate_synthetic.py
  GATE: Video → SQLite with tracks + keyframes (no depth, no API)

SPRINT 2: Scene Understanding (Days 4-6)
  Day 4: AgentState, ToolRegistry, orchestrator, ingest_from_db
  Day 5: calibrate_from_person_height (THE critical tool)
  Day 6: classify_scene_type, vlm_scene_layout, depth_scene_analysis
  GATE: DB → BEV-calibrated tracks + scene classification

SPRINT 3: Zone Discovery (Days 7-10)
  Day 7:  compute_dwell_points (BEV, confinement filter)
  Day 8:  strategy_dwell_clustering + strategy_occupancy_grid
  Day 9:  strategy_trajectory_graph + fuse_zone_candidates
  Day 10: vlm_detect_structures + debug visualizations for all
  GATE: Ensemble produces fused zones with debug plots

SPRINT 4: VLM Toolkit + Analytics (Days 11-14)
  Day 11: OpenRouter client, crop_zone_images, depth_zone_analysis
  Day 12: vlm_object_inventory + vlm_signage_reader
  Day 13: vlm_zone_classifier + vlm_zone_describer + merge_zone_registry
  Day 14: compute_zone_analytics + compute_flow_analytics + temporal + spatial
  GATE: Named, typed, described zones with full analytics

SPRINT 5: Validation + Viz (Days 15-17)
  Day 15: validate_zones, quality_gate (agentic re-run)
  Day 16: plan_visualizations (agentic), render_all_visualizations
  Day 17: render_3d_scene, export_dashboard_bundle, report.json
  GATE: Complete Module B with validated output + viz data

SPRINT 6: Dashboard + Polish (Days 18-20)
  Day 18: React scaffold, KPIRibbon, ZoneMapPerspective, ZoneMapBEV
  Day 19: SankeyFlow, TemporalHeatmap, ZoneDetailPanel, TrajectoryReplay
  Day 20: Three.js viewer, DebugInspector, integration tests, e2e demo
  GATE: Full system working end-to-end
```

---

## 12. APPENDIX: KEY ALGORITHMS

### A. Person-Height Calibration Pseudocode

```
INPUT: tracks DataFrame with bbox_h, y_center columns
OUTPUT: homography matrix, BEV parameters

1. Filter high-confidence detections (conf > 0.5, bbox_h > 20px)
2. Bin by y-center into 20 bands
3. Compute median bbox_h per band (need ≥ 5 samples per band)
4. Fit model: bbox_h = K / (y - y_vanishing_point)
   using least_squares with bounds
5. Extract focal_length = K / person_height_meters
6. Compute 4 reference points at image corners → ground plane positions
7. cv2.findHomography(src_points, dst_points) → H
8. Transform all track points: bev = H @ pixel
9. Compute speed in m/s from BEV displacements
10. Validate: check median walking speed ∈ [0.5, 3.0] m/s
```

### B. Context-Aware Dwell Detection

```
FOR each track (in BEV meters):
  Compute speed_m_s at each point
  Segment into "move" (speed > threshold) and "slow" segments
  
  FOR each "slow" segment:
    centroid = mean position of segment points
    confinement_radius = max distance from centroid to any point
    duration = segment time span
    curvature = sum of absolute heading changes
    
    IS_DWELL = (
      duration >= min_dwell_seconds AND
      confinement_radius < 2.0 meters AND
      curvature > 0.5 radians  # Loitering, not straight slow walk
    )
```

### C. VLM Multi-Turn Zone Enrichment Flow

```
FOR each zone:
  1. crop_zone_images: standard (+20%) and wide (+40%) crops
  2. depth_zone_analysis: get physical dimensions from depth crop
  3. vlm_object_inventory: "list every object" → objects list
  4. vlm_signage_reader: "read all text" → signage, business name
  5. vlm_zone_classifier: objects + signage + behavior → zone_type
     IF confidence < 0.5:
       RETRY with wide crop + full behavioral context
       IF still < 0.5:
         RETRY with full frame + zone highlighted
     IF all fail: zone_type = "unknown"
  6. vlm_zone_describer: everything → rich text description
```

### D. Ensemble Fusion Voting

```
1. Create voting grid (4x BEV resolution)
2. Rasterize each candidate polygon, weighted by confidence
3. Per cell: count strategies with vote > 0.1
4. STRONG zone: ≥ 2 strategies agree
   WEAK zone: 1 strategy but confidence > 0.7
5. Morphological close(5x5) + open(3x3)
6. Connected components → final zones
7. Filter by min_zone_area_m2
```

---

**END OF SPECIFICATION**

This is the single source of truth. Module A has zero API deps.
Depth is a Module B knowledge tool (reference frame + zone crops).
VLM is a 5-tool toolkit (objects, signage, classify, describe, structures).
Calibration uses person-height regression from tracking data.
Build in sprint order. Every tool produces debug visualizations.
