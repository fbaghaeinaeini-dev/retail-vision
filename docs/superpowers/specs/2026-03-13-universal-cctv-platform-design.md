# Universal CCTV Analytics Platform — Design Specification

**Date:** 2026-03-13
**Status:** Approved
**Scope:** Generalize RetailVision into a universal, zero-configuration, people-and-vehicle analytics platform for any CCTV environment

---

## 1. Vision & Product Boundary

### 1.1 Core Promise
**One input. Zero configuration. Any environment.**

The user provides a video file. The system automatically detects the environment type, calibrates the camera, discovers functional zones, computes analytics, identifies safety events, and produces a comprehensive report — without any manual configuration.

### 1.2 Scope
- **People-centric analytics everywhere** — tracks people (and vehicles where relevant) across any CCTV environment
- **Batch processing** — offline analysis of recorded video files (not real-time streaming)
- **Zero-parameter pipeline** — auto-detects resolution, camera type, indoor/outdoor, scene type, crowd density, lighting, and generates all downstream parameters from a single video file input

### 1.3 Target Environments (Priority Order)
1. Shopping malls / retail (current strength)
2. Restaurants / hospitality
3. Airports / transit hubs
4. Outdoor markets / plazas
5. Parking lots
6. Warehouses / logistics
7. Construction sites
8. University campuses
9. Traffic scenarios
10. Petrol stations
11. Hospitals / clinics
12. Schools
13. Perimeter protection / borders
14. Train stations

### 1.4 Out of Scope (Current Phase)
- Real-time / live streaming (future)
- Edge deployment (future)
- Multi-camera cross-camera tracking (future)
- Dashboard / UI changes (existing demo system is sufficient)
- Deployment infrastructure changes

---

## 2. Architecture Overview

### 2.1 Pipeline Phases

```
USER INPUT: video file (only input)
     ↓
PHASE 0: Scene Profiling (NEW)
     ↓
PHASE 1: Unified Tracking (REBUILT)
     ↓
PHASE 2: Multi-Signal Calibration (REDESIGNED)
     ↓
PHASE 3: Zone Discovery (REDESIGNED)
     ↓
PHASE 4: Analytics + Safety (GENERALIZED)
     ↓
PHASE 5: Validation + Quality Gate (ADAPTED)
     ↓
PHASE 6: Export (ADAPTED)
     ↓
OUTPUT: report.json with confidence metadata
```

### 2.2 Key Architectural Principles

1. **Never trust a model silently** — every output carries a confidence score
2. **Graceful degradation** — when a component fails, fall back and report, don't crash or produce garbage
3. **VLM calls are precious** — minimize API calls; VLM configures, local models execute
4. **Sensor fusion over single-signal** — calibration, zone discovery, and safety all use multiple independent signals
5. **Scene-adaptive everything** — no hardcoded parameters; Scene Profiler generates bespoke configuration per video
6. **Honest reporting** — system explicitly states what it can't determine rather than guessing

---

## 3. Phase 0: Scene Profiling

The heart of zero-configuration. Runs ONCE at the start, replaces all manual configuration.

### 3.1 Step 0a: Format Validation & Frame Sampling
- Validate video format (detect proprietary formats: .dav, raw .264/.265, .PSS — provide actionable error messages)
- Detect multi-camera composite images (quad/grid views) — auto-split if detected
- Extract 5-10 frames spread across video (first, 25%, 50%, 75%, last)
- Compute: resolution, FPS, duration, aspect ratio, frame stability (is camera moving?)
- Measure footage quality score (BRISQUE or blockiness metric)
- Detect PTZ camera motion via global optical flow — segment video into stable intervals

### 3.2 Step 0b: Camera Type Detection
- **Fisheye detection**: lens distortion analysis from GeoCalib or VLM identification
  - If fisheye → dewarp to rectilinear before downstream processing
  - Consider Depth Any Camera (CVPR 2025, MIT license) for fisheye-native depth
- **Overhead detection**: if camera tilt >70° from horizontal, switch to head-detection mode
- **IR/thermal detection**: histogram analysis (bimodal, narrow dynamic range) or VLM
  - If thermal → flag degraded mode, disable ReID, adjust detector confidence

### 3.3 Step 0c: Camera Intrinsics Estimation
- Run a camera intrinsics estimator on reference frame (ONCE)
- **Model options** (select based on licensing review at implementation time):
  - GeoCalib (ECCV 2024) — verify license permits commercial use before adopting
  - Deep-BrownConrady (Jan 2025) — predicts distortion from single image
  - Classical vanishing point detection — no licensing risk, works on structured scenes
  - If no suitable licensed model: fall back to EXIF/metadata extraction + VLM-assisted estimation
- Outputs: focal length, principal point, vertical direction, camera tilt angle, horizon line, distortion parameters
- Confidence score based on scene structure (structured indoor = high, featureless outdoor = low)
- **License gate:** Must confirm commercial-use license before integrating any model into the pipeline

### 3.4 Step 0d: DA3-Metric — Depth Estimation
- Run Depth Anything V3 Metric (Large) on reference frame (ONCE)
- Outputs: metric depth map in meters, per-pixel distance
- Ground plane extraction via RANSAC on depth-derived point cloud
- Ground plane mask (walkable surfaces)
- Used for: scene understanding, spatial layout, supplementary calibration signal
- NOT used as: primary calibration (see Phase 2)
- Confidence score based on depth consistency and edge alignment

### 3.5 Step 0e: VLM Scene Classification (MOVED BEFORE SEGMENTATION)
- Send reference frame + depth visualization to VLM (1 call)
- This runs BEFORE segmentation so it can inform segmentation prompts
- Structured output with confidence scores:
  ```
  environment: indoor | outdoor | semi-outdoor (confidence: 0.95)
  venue_type: airport_terminal (confidence: 0.88)
  crowd_density: moderate (confidence: 0.82)
  lighting: artificial (confidence: 0.91)
  camera: fixed, elevated ~5m, normal lens (confidence: 0.85)
  reflective_surfaces: glass_wall_east_side (confidence: 0.70)
  uniform_clothing: false
  segmentation_prompts: ["gate area", "seating", "security checkpoint",
    "queue barrier", "display screen", "luggage", "corridor"]
  ```

### 3.6 Step 0f: Open-Vocabulary Segmentation (AFTER scene classification)
- Run Grounded SAM 2 (Grounding DINO + SAM 2) on reference frame (1-2 runs total)
- Text prompts from VLM scene classification output (Step 0e) — scene-adapted, not generic
- Universal base prompts always included: floor, wall, door, column, person, vehicle, chair, table, sign
- Scene-specific prompts added from VLM: e.g., for airport → "gate area", "security checkpoint", "luggage carousel"
- SAHI tiling for small/distant objects if needed
- Produces `SceneSemanticMap` used by: calibration (ground mask), tracking (walkable surface filter), zone discovery (structural priors), zone naming (object inventory)

### 3.7 Step 0g: Adaptive Configuration Generation
Based on all Scene Profiler outputs, generate:
- **Detector config**: model tier, confidence threshold, SAHI on/off
- **Tracker config**: buffer size, ReID mode (full/motion-only/lightweight), max-age
- **Calibration strategy**: which signals to trust, weights for fusion
- **Zone discovery params**: clustering parameters, structural prior weights
- **Analytics interpretation rules**: what "normal dwell" means for this environment, anomaly thresholds
- **Safety rule set**: which Tier 2 models to activate, severity definitions
- **Zone taxonomy hints**: expected zone types for this environment

### 3.8 Step 0h: Adaptive Prompt Context Block
VLM generates a prompt context block injected into ALL downstream prompts:
```
Scene Context (auto-generated):
- Environment: Airport terminal, indoor, artificial lighting
- Expected zone types: gate areas, security checkpoints, lounges, retail shops, food courts, boarding corridors
- Crowd behavior: fast transit corridors, long dwell at gates, queuing at security
- "Dwell" definition: >60s (airports have longer wait tolerance)
- Key analytics: queue length, gate utilization, corridor throughput
- Anomaly signals: counter-flow, restricted area entry, abandoned luggage zones
- Safety priorities: crowd density at gates, queue overflow at security, unattended bags
```

This context block adapts:
- Gate 1 (strategy selection) reasoning
- Phase 3 zone classification prompts
- Phase 4 analytics interpretation
- Gate 3 classification review
- Chat API system prompt (domain-appropriate language)

### 3.9 VLM Budget — Full Pipeline

| Phase | VLM Calls | Purpose |
|-------|-----------|---------|
| Phase 0: Scene classification | 1 | Classify environment + generate segmentation prompts |
| Phase 0: Prompt context generation | 1 | Generate adaptive prompt block + safety rules + analytics interpretation |
| Phase 0: Config generation | 1 | Generate detector/tracker/clustering parameters |
| Gate 1: Strategy validation | 1 | Review scene profile, validate zone discovery approach |
| Phase 3: Zone naming | N (1 per zone) | Classify + name each discovered zone |
| Gate 2: Zone review | 1 | Review discovered zones, may trigger retry |
| Gate 3: Classification review | 1 | Validate zone types against behavioral data |
| **TOTAL** | **6 + N** | **For 10 zones: ~16 calls** |
| **Retry budget** | +3-5 | Gate-triggered retries (worst case) |
| **Hard ceiling** | **25** | System stops making VLM calls beyond this |

**Note:** All gates from the existing system are preserved but receive scene-adapted prompts from the Phase 0 context block. Gates are NOT removed — they are enhanced.

---

## 4. Phase 1: Unified Tracking & Re-Identification

### 4.1 Detection — NMS-Free, Multi-Class

**Primary detector:** RF-DETR-Medium (Apache 2.0, ICLR 2026)
- pip-installable (`pip install rfdetr`)
- NMS-free (transformer bipartite matching) — eliminates duplicate boxes at source
- Multi-class: person + vehicle in one pass
- Requires TensorRT ≥10.3 for competitive speed (mandate in deployment requirements)

**Adaptive detection modes (selected by Scene Profiler):**

| Scene Condition | Detection Strategy |
|----------------|-------------------|
| Standard (good lighting, moderate density) | RF-DETR-Medium, single-pass, 560x560 |
| Distant/small subjects (parking, wide-angle) | RF-DETR-Medium + SAHI (tiled inference) — **NOTE:** SAHI's tile-merge step uses NMS internally for cross-tile deduplication; must validate compatibility with RF-DETR's NMS-free output or implement custom tile-merge using embedding similarity instead of IoU-NMS |
| Dense crowds (>50 tightly packed) | Density estimation model (CSRNet/DM-Count) for counting — individual tracking unavailable |
| Night/low-light | CLAHE preprocessing + lowered confidence threshold |
| IR/thermal | Flag degraded mode, adjusted thresholds, warn in output |
| Overhead | Head detection mode (adjust detection classes) |

**Fallback detector:** YOLOv11-M (for users who accept AGPL licensing)

**Detector abstraction:** Pipeline-agnostic `Detector` interface returns standardized `Detection(bbox, confidence, class_id, track_id, embedding)` objects. Models are swappable without pipeline changes.

### 4.2 Deep Re-Identification

**Tiered ReID strategy (selected by Scene Profiler):**

| Mode | When | Model | Cost |
|------|------|-------|------|
| **Full ReID** | Diverse clothing, moderate density | OSNet x1.0 (2.2M params, ~8.5MB, ~2ms/crop) via BoxMOT | ~15-25ms/frame |
| **Lightweight ReID** | Resource-constrained | OSNet x0.25 (0.2M params, ~1MB, <1ms/crop) | ~5ms/frame |
| **Motion-only** | Uniforms detected, or extreme density | ByteTrack (no ReID) | ~1ms/frame (720 FPS) |

**Uniform detection:** Appearance feature clustering during first 1000 frames. Low inter-person variance → uniform detected → switch to motion-only mode.

**Separate ReID models per entity class:**
- Person ReID: OSNet or CLIP-ReID (person appearance features)
- Vehicle ReID: CLIP-ReID VehicleID checkpoint (vehicle appearance features — color, make, model)
- Same tracking pipeline, different embedding spaces

### 4.3 Multi-Cue Association

Cost matrix for Hungarian algorithm assignment:
```
C_ij = w_appearance * cosine_distance(reid_i, reid_j)    [if ReID enabled]
     + w_motion    * kalman_prediction_distance(i, j)
     + w_spatial   * iou_distance(bbox_i, bbox_j)
     + w_depth     * depth_consistency(i, j)              [if depth available]
     + w_size      * aspect_ratio_consistency(i, j)
```
Weights adapted by Scene Profiler based on scene conditions.

### 4.4 Track Lifecycle Manager

| State | Description | Transition |
|-------|-------------|-----------|
| **Birth** | New detection unmatched for 3 consecutive frames | → Active |
| **Active** | Matched and updated every frame | → Occluded (if unmatched) |
| **Occluded** | Unmatched but motion-predicted, kept alive up to N frames (scene-dependent) | → Active (if re-matched via ReID) or → Death |
| **Merge** | Two tracks with >0.85 ReID cosine similarity + temporal overlap impossibility | Retrospectively merge into one identity |
| **Death** | Unmatched beyond max-age | Track finalized |

### 4.5 Track Quality Scoring v2

```
quality = 0.20 * duration_norm
        + 0.15 * detection_count_norm
        + 0.20 * avg_confidence
        + 0.15 * completeness
        + 0.15 * smoothness
        + 0.10 * depth_consistency     [track depth should be physically plausible]
        + 0.05 * ground_plane_adherence [positions should lie on walkable surfaces]
```

Tracks failing ground plane adherence are likely ghosts (reflections, shadows, screen detections).

### 4.6 Post-Track Deduplication

After full video processing:
1. Extract average ReID embedding per track (multiple crops averaged for robustness)
2. Cluster track embeddings (hierarchical clustering, cosine similarity >0.7)
3. Apply temporal constraints (don't merge tracks that overlap in time)
4. Apply spatial constraints (person can't teleport across frame)
5. Produce "unique identity" count with explicit error margin (±10-15%)
6. Link re-entries: person left zone A, returned 10 min later → same identity

### 4.7 Lightweight Safety Models (Tier 2)

Run on keyframes only (every 5s), activated conditionally by Scene Profiler:

| Model | Size | Activated For | False Positive Mitigation |
|-------|------|--------------|--------------------------|
| Fire/smoke (YOLOv8n fine-tuned) | ~6MB | All scenes | Require 3+ consecutive frame detections before flagging |
| PPE (helmet/vest, YOLOv8n fine-tuned) | ~6MB | Construction, warehouse, factory (close-range cameras only) | Min pixel height threshold for reliable detection |

**Not shipped in initial version (Tier 3 roadmap):**
- Spill detection (no pretrained model exists — requires custom training)
- PPE at CCTV distance (needs super-resolution research)
- Water/transparent liquid detection (unsolved problem)

---

## 5. Phase 2: Multi-Signal Calibration Fusion

### 5.1 Architecture — Three Signals Constrain Each Other

Calibration runs AFTER tracking (needs person detections) and IMPROVES OVER TIME as more people are observed.

**Signal A: GeoCalib** (computed in Phase 0)
- Camera intrinsics: focal length, principal point, tilt angle
- Confidence: high for structured scenes, low for featureless

**Signal B: DA3-Metric depth** (computed in Phase 0)
- Per-pixel metric depth, ground plane
- Confidence: high for clean well-lit, low for compressed/overhead/IR

**Signal C: Person-Height Regression** (improves over time)
- Start with 1.7m population prior
- For each tracked person at position (u, v):
  ```
  height_pixels  = bounding box height
  depth_da3      = DA3 depth at (u, v)
  focal_geocalib = GeoCalib focal length

  h_from_da3     = height_pixels * depth_da3 / focal_geocalib
  h_from_geometry = height_pixels * (camera_height / vanishing_ratio)
  ```
- Cross-validate estimates: agreement within 15% → high confidence
- Feed each observation back into Bayesian calibration estimate
- Outlier rejection: children, very tall people identified and excluded from regression
- Convergence: 5 people → low confidence, 30+ people → medium, 100+ people → high

### 5.2 Fusion Algorithm — MAP Estimation

**State vector** to estimate:
```
θ = [f, h_cam, tilt, s]
where:
  f     = focal length (pixels)
  h_cam = camera height (meters)
  tilt  = camera tilt from horizontal (radians)
  s     = global scale correction factor
```

**Prior** (from Phase 0):
```
θ_prior = [f_geocalib, h_da3, tilt_geocalib, 1.0]
Σ_prior = diag([σ²_f, σ²_h, σ²_tilt, σ²_s])

where σ values reflect confidence of each Phase 0 signal:
  - GeoCalib high confidence → σ_f = 50px, σ_tilt = 0.05 rad
  - GeoCalib low confidence  → σ_f = 200px, σ_tilt = 0.2 rad
  - DA3 camera height derived from depth map ground plane distance:
    h_da3 = median(depth_map[ground_mask]) * sin(tilt_geocalib)
    σ_h depends on DA3 confidence (high: 0.5m, low: 2.0m)
```

**Observation model** (each tracked person):
```
For person i at pixel position (u_i, v_i) with bounding box height p_i pixels:

  Expected pixel height given state θ:
    p̂_i = f * H_person / d_i(θ)

  where:
    H_person ~ N(1.70, 0.10²)  — population height prior
    d_i(θ)   = h_cam / sin(tilt + atan((v_i - cy) / f))  — geometric distance

  Observation: p_i (measured pixel height)

  Cross-validation with DA3:
    d_da3_i = depth_map[u_i, v_i] * s  — scaled DA3 depth
    Residual: |d_i(θ) - d_da3_i|
    If residual < 20%: both signals agree, reduce uncertainty
    If residual > 40%: one signal is unreliable, increase that signal's σ
```

**Update rule** (iterative MAP):
```
After accumulating N person observations (batch every 1000 frames):
  θ_MAP = argmax P(θ | observations) ∝ P(observations | θ) * P(θ | prior)

  Solved via Levenberg-Marquardt optimization on the residual:
    r_i = p_i - f * H_person / d_i(θ)   for each person i

  With regularization toward prior:
    r_prior = (θ - θ_prior) / σ_prior
```

**Convergence criterion:**
```
  Calibration confidence = function of:
    - Number of person observations (N)
    - Spread of observations across depth range
    - Consistency of residuals

  N < 5:   confidence = "low"
  N < 30:  confidence = "medium"
  N ≥ 30 AND residual_std < 0.15: confidence = "high"
```

**Homography computation** (from converged state θ):
```
  H = K_bev⁻¹ * R(tilt) * K_cam

  where:
    K_cam = [[f, 0, cx], [0, f, cy], [0, 0, 1]]  — camera intrinsics
    R(tilt) = rotation matrix from camera tilt
    K_bev = BEV scaling matrix (meters per pixel in bird's eye view)

  The homography maps ground-plane pixels to metric BEV coordinates.
  Non-ground pixels (above ground plane mask) are not transformed.
```

### 5.3 Fallback Chain

| Priority | Method | When Used | Confidence |
|----------|--------|-----------|-----------|
| 1 | Multi-signal fusion (GeoCalib + DA3 + person-height) | ≥3 people detected, all signals available | HIGH |
| 2 | GeoCalib + person-height (no depth) | DA3 fails (overhead, IR, extreme compression) | MEDIUM-HIGH |
| 3 | Person-height only | GeoCalib fails (featureless scene), ≥3 people detected | MEDIUM |
| 4 | GeoCalib + DA3 (no people) | Empty scene, no person detections | MEDIUM-LOW |
| 5 | VLM estimate + fixed scale | All models fail | LOW (explicitly flagged) |

### 5.4 Output: SceneGeometry

```python
@dataclass
class SceneGeometry:
    homography: np.ndarray          # 3x3 pixel → BEV meters
    depth_map: np.ndarray           # Per-pixel metric depth
    ground_plane_mask: np.ndarray   # Boolean: where people can walk
    camera_height_m: float          # Estimated camera height
    camera_tilt_deg: float          # Tilt from horizontal
    focal_length_px: float          # Estimated focal length
    distortion_coeffs: np.ndarray   # Lens distortion (from GeoCalib)
    px_per_meter: float             # Average scale factor
    confidence: str                 # "high" / "medium" / "low"
    calibration_method: str         # Which fusion path was used
    num_calibration_points: int     # How many people contributed
    convergence_error_m: float      # Estimated metric accuracy
```

---

## 6. Phase 3: Zone Discovery

### 6.1 Principle: Structure-First, Behavior-Second, VLM-Validates

Replace the current 3 hardcoded strategies + rigid profiles with a unified approach.

### 6.2 Layer 1: Structural Zone Seeds (from segmentation)

Using the SceneSemanticMap from Phase 0:
- Cluster semantically related objects (tables + chairs = seating cluster)
- Identify architectural boundaries (walls, columns, barriers → zone edges)
- Detect functional infrastructure (doors → entrances, counters → service points)
- Output: candidate structural zones with semantic labels and physical boundaries

### 6.3 Layer 2: Behavioral Zone Discovery (from tracking)

Compute spatiotemporal feature map from all tracks:
- **Dwell density**: where people/vehicles stop (speed < threshold)
- **Flow density**: where people/vehicles move through
- **Speed field**: fast corridors vs slow zones
- **Temporal variance**: always busy vs periodic activity

Adaptive clustering on feature map:
- Parameters generated by Scene Profiler (not hardcoded)
- Density-based clustering (DBSCAN/HDBSCAN with scene-adapted epsilon)
- Output: candidate behavioral zones with activity signatures

### 6.4 Layer 3: Structure-Behavior Fusion

Match structural zones to behavioral zones (IoU + semantic coherence):

| Outcome | Meaning | Example |
|---------|---------|---------|
| **Structure + Behavior agree** | High-confidence zone | Tables + chairs where people sit → confirmed seating area |
| **Structure only** (no activity) | Dormant zone | Stage with no current event → dormant performance area |
| **Behavior only** (no structure) | Emergent zone | Queue formed in open space, gathering point, informal pathway |

Snap behavioral boundaries to structural edges (columns, walls, planters).

### 6.5 Layer 4: VLM Validation & Naming

For each fused zone, VLM receives:
- Cropped image of zone
- Semantic labels within zone (from segmentation)
- Behavioral metrics (dwell, flow, visits)
- Scene context block (from Phase 0)

VLM assigns:
- **Business name** (if signage detected by segmentation OCR or VLM)
- **Functional type** from universal taxonomy (see 6.6)
- **Natural language description**
- **Confidence score**

Prompts are scene-adapted: airport terminology for airports, retail for malls, industrial for warehouses.

**VLM calls: 1 per zone (batched where possible)**

### 6.6 Universal Zone Taxonomy

Root categories (structural — always apply):
```
├── Dwelling     — where people/vehicles stop intentionally
├── Service      — where transactions/interactions happen
├── Transit      — movement corridors and paths
├── Queue        — ordered waiting
├── Staging      — temporary holding (parking, loading)
├── Activity     — active work or purpose-specific action
├── Restricted   — access-controlled areas
├── Monitoring   — observation points, checkpoints
└── Open         — unstructured multipurpose space
```

**Subtypes are VLM-generated per scene**, not from a fixed list. Examples:

| Environment | VLM-Generated Subtypes |
|------------|----------------------|
| Airport | gate_area, security_checkpoint, lounge, boarding_corridor, baggage_claim |
| Petrol station | fuel_pump_bay, payment_kiosk, car_wash_queue, convenience_store |
| Hospital | emergency_entrance, triage_waiting, ambulance_bay, staff_corridor |
| School | classroom_entrance, playground, pickup_zone, cafeteria, hallway |
| Border | checkpoint_gate, inspection_bay, holding_area, patrol_path, exclusion_zone |
| Train station | platform, ticket_hall, turnstile_bank, waiting_shelter |
| Construction | active_work_zone, material_staging, equipment_area, safety_perimeter |
| Parking lot | parking_bay, drive_aisle, pedestrian_walkway, entrance_barrier |
| Traffic | vehicle_queue, pedestrian_crossing, turning_lane, bus_stop |

If the system encounters an environment never anticipated, the VLM creates appropriate types from scratch.

---

## 7. Phase 4: Analytics + Safety

### 7.1 Universal Metrics (computed for ALL zones)

| Metric | Description | Entity Split |
|--------|-------------|-------------|
| **Occupancy** | Entities present over time (avg, max, timeseries) | People / Vehicles |
| **Dwell distribution** | Duration statistics (median, p95, histogram) | People / Vehicles |
| **Flow rate** | Entities entering/leaving per time unit | People / Vehicles |
| **Transitions** | Zone-to-zone movement probability (Markov chain) | People / Vehicles |
| **Density** | Entities per square meter over time | People / Vehicles |
| **Temporal pattern** | Activity by hour (rush detection) | Combined |
| **Utilization** | Active time / total time | Per zone |
| **Queue metrics** | Wait time, length, service rate (when sequential waiting detected) | People |
| **Speed profile** | Movement speed distribution within zone | People / Vehicles |
| **Anomaly score** | Deviation from zone's normal pattern | Combined |

### 7.2 Scene-Adaptive Analytics Interpretation

The Scene Profiler generates interpretation rules defining what's "normal":

```
# Example: Petrol station (auto-generated by VLM)
fuel_pump_bay:
  normal_dwell: 3-8 min (refueling)
  anomaly_dwell: >15 min (abandoned vehicle?)

payment_kiosk:
  normal_queue: 0-2 min
  alert_queue: >5 min (staffing issue)

drive_aisle:
  normal_speed: 5-15 km/h
  safety_alert: >30 km/h

# Example: Border checkpoint (auto-generated by VLM)
checkpoint_gate:
  normal_queue: 5-30 min
  capacity_alert: >60 min

inspection_bay:
  counter_flow: CRITICAL anomaly

holding_area:
  extended_dwell: expected, no upper anomaly
```

### 7.3 Safety Intelligence Layer

**Tier 1: Tracking-Based Safety (FREE — pure math on tracking data)**

Always computed:
- Fall detection (sudden trajectory + bbox change)
- Person immobile too long (potential collapse/medical)
- Counter-flow / wrong-way movement
- Crowd density exceeding threshold
- Running in non-running zone
- Restricted zone entry
- Loitering at perimeter / fence line
- Vehicle-pedestrian proximity alert
- Speed violation (vehicle in pedestrian area)
- Queue overflow (unbounded growth)
- Evacuation pattern (mass directional flow)
- Temporal anomaly (activity at unusual hour)
- Capacity creep (zone gradually overcrowding)

**Tier 2: Lightweight Local Models (activated conditionally)**

| Detector | Activation Condition | Runtime |
|----------|---------------------|---------|
| Fire/smoke | All scenes | Keyframes every 5s, 3-frame confirmation |
| PPE (helmet/vest) | Construction, warehouse, factory — close-range cameras only | Keyframes every 5s |

**Tier 3: Roadmap (not shipped initially)**
- Spill/debris detection (requires custom model training)
- PPE at CCTV distance (needs super-resolution)
- Abandoned object detection (detector + tracker + temporal rules — complex system)

**Safety output per zone:**
```json
{
  "safety": {
    "events": [...],
    "risk_score": 0.35,
    "compliance": {
      "fire_exit_clear": true,
      "max_occupancy_respected": true,
      "ppe_compliance_rate": 0.92
    },
    "tier_1_confidence": "high",
    "tier_2_confidence": "medium",
    "degradation_notes": ["PPE detection limited to <10m range"]
  }
}
```

### 7.4 Segmentation-Assisted Safety (static, from Phase 0 runs)

From the 1-2 segmentation runs already budgeted:
- Fire exit locations mapped → track if blocked by checking for static objects in exit zone mask
- Pathway masks defined → track if obstructed
- Safety equipment inventory (extinguishers, first aid, AED) → mapped for audit

These become static masks that Tier 1 tracking checks against at zero additional cost.

---

## 8. Phase 5: Validation + Quality Gate

### 8.1 Quality Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| Silhouette score | Clustering quality of zone discovery | > 0.3 |
| Coverage % | % of tracked activity within discovered zones | > 0.85 |
| VLM agreement | Classification consistency with behavioral data | > 0.7 |
| Count sanity | Consistency of aggregated metrics | > 0.5 |
| Multi-signal % | % of zones confirmed by both structure + behavior | ideal = 1.0 |
| Calibration confidence | Convergence of multi-signal calibration | report as metadata |
| Overall score | Weighted average | > 0.40 to pass |

### 8.2 Retry Logic

If quality gate fails:
- Relax clustering parameters (spatial eps ×1.3, min dwell ×0.8)
- Accept single-signal zones (structure-only or behavior-only)
- Re-run Phase 2-4 (no extra VLM calls for Phase 2-4 retry)
- Maximum 2 retries before accepting best result with warnings

---

## 9. Phase 6: Export

### 9.1 Report Structure

```json
{
  "meta": {
    "video_id": "...",
    "duration_seconds": 1800,
    "scene_profile": {
      "environment": "airport_terminal",
      "venue_type_confidence": 0.88,
      "camera_type": "fixed_elevated",
      "lighting": "artificial",
      "crowd_density": "moderate",
      "footage_quality_score": 0.72,
      "ir_thermal": false,
      "fisheye": false,
      "composite_image": false
    },
    "calibration": {
      "method": "multi_signal_fusion",
      "confidence": "high",
      "num_calibration_points": 87,
      "convergence_error_m": 0.15,
      "signals_used": ["geocalib", "da3_metric", "person_height"]
    },
    "tracking": {
      "detector": "rf_detr_medium",
      "reid_mode": "full",
      "total_tracks": 312,
      "unique_identities": 198,
      "unique_identity_margin": "±15%",
      "entity_types": ["person", "vehicle"]
    },
    "quality": {
      "overall_score": 0.725,
      "passed": true,
      "metrics": { ... }
    },
    "warnings": [
      "Reflective surface detected on east wall — counts may include reflections",
      "Footage compression is moderate (CRF ~30)"
    ]
  },
  "zones": {
    "zone_001": {
      "zone_id": "zone_001",
      "zone_type": "gate_area",
      "zone_type_confidence": 0.92,
      "business_name": "Gate B12",
      "description": "Boarding gate with seating and queue area",
      "discovery_method": "structure+behavior",
      "polygon_bev": [...],
      "polygon_pixel": [...],
      "area_m2": 45.2,
      "area_confidence": "high",
      "semantic_objects": ["chair", "display_screen", "queue_barrier"],
      "analytics": {
        "total_visits": 245,
        "unique_visitors": 128,
        "unique_visitor_margin": "±15%",
        "entity_breakdown": {
          "person": { "visits": 245, "unique": 128 },
          "vehicle": { "visits": 0, "unique": 0 }
        },
        "avg_dwell_seconds": 312,
        "median_dwell_seconds": 280,
        "p95_dwell_seconds": 840,
        "peak_hour": 14,
        "avg_occupancy": 8.3,
        "max_occupancy": 22,
        "utilization": 0.78,
        "density_per_m2_hr": 5.4
      },
      "safety": {
        "events": [],
        "risk_score": 0.12,
        "compliance": { ... },
        "confidence": "high"
      },
      "degradation_warnings": []
    }
  },
  "flow": {
    "transitions": [
      {"from": "zone_001", "to": "zone_003", "count": 45, "probability": 0.18, "entity_type": "person"}
    ]
  },
  "safety_timeline": [
    {
      "timestamp": "00:14:23",
      "frame_idx": 25614,
      "type": "crowd_density_warning",
      "severity": "warning",
      "zone": "zone_002",
      "tier": 1,
      "confidence": 0.85,
      "description": "Crowd density reached 4.2 people/m² (threshold: 4.0)"
    }
  ]
}
```

---

## 10. Edge Case Handling

### 10.1 Critical Edge Cases (Must Handle)

| Edge Case | Detection Method | Response |
|-----------|-----------------|----------|
| **Non-standard video format** | ffmpeg decode failure analysis | Actionable error: "This appears to be a Dahua .dav file. Export to MP4 using SmartPSS first." |
| **Multi-camera composite** | Image analysis (regular borders, content discontinuities) | Auto-split into individual views, process independently |
| **Fisheye lens** | GeoCalib distortion detection or VLM | Dewarp to rectilinear before processing; or use Depth Any Camera |
| **PTZ camera motion** | Global optical flow exceeding threshold | Segment video into stable intervals, process each independently, warn about motion gaps |
| **IR/thermal at night** | Histogram analysis, VLM | Flag degraded mode, disable ReID, adjust thresholds, warn in output |

### 10.2 High-Priority Edge Cases

| Edge Case | Detection Method | Response |
|-----------|-----------------|----------|
| **Reflective surfaces** | VLM identifies glass/mirrors in scene description | Define exclusion zones, suppress symmetric detections |
| **People in uniforms** | Appearance clustering (low inter-person variance) | Switch to motion-only tracking, disable unique visitor claims |
| **Dense crowds (>50 packed)** | Real-time density estimation from detection count vs area | Switch to density estimation model, report: "Individual tracking unavailable" |
| **Overhead camera** | Camera tilt estimation >70° | Head detection mode, skip depth-based calibration |
| **Empty scene (0 people)** | Zero detection count | Static scene analysis only, report: "No activity detected" |

### 10.3 Medium-Priority Edge Cases

| Edge Case | Detection Method | Response |
|-----------|-----------------|----------|
| **Very short video (<5 min)** | Duration check | Skip zone discovery, provide frame-level analytics only |
| **Very low resolution (<720p)** | Resolution check | Report minimum threshold, adjust detection thresholds upward |
| **Extreme compression** | BRISQUE / blockiness score | Report degraded quality, raise detection confidence thresholds |
| **Children** | Detection size clustering (bimodal height distribution) | Use height distribution not fixed 1.7m, adjust motion model |
| **Animals** | VLM identifies animal-rich environment | Stricter person classification, secondary filter |
| **Running/fast motion** | Velocity anomaly in tracker | Increase association radius, weight ReID over spatial proximity |

---

## 11. Model Stack & Resource Requirements

### 11.1 Models Used

| Model | Purpose | Size | License | Runs On |
|-------|---------|------|---------|---------|
| RF-DETR-Medium | Object detection (person + vehicle) | ~130MB | Apache 2.0 | GPU (local) |
| OSNet x1.0 | Person ReID | ~8.5MB | MIT | GPU/CPU |
| CLIP-ReID VehicleID | Vehicle ReID | ~350MB | MIT | GPU |
| DA3-Metric Large | Metric depth estimation | ~1.3GB | Apache 2.0 | GPU (local) or Replicate API |
| GeoCalib | Camera intrinsics estimation | ~200MB | Research | GPU (local) |
| Grounded SAM 2 | Open-vocab segmentation | ~2GB | Apache 2.0 | GPU (local) or Replicate API |
| YOLOv8n (fire/smoke) | Fire/smoke detection | ~6MB | AGPL (consider training own) | CPU |
| YOLOv8n (PPE) | PPE detection | ~6MB | AGPL (consider training own) | CPU |
| Qwen3-VL (via OpenRouter) | Scene classification, zone naming, prompt generation | Remote | API | Cloud (API call) |

### 11.2 GPU Memory Requirements

| Configuration | VRAM Needed | Strategy |
|--------------|-------------|----------|
| **Minimal (sequential model loading)** | 6-8 GB | Load one model at a time, swap |
| **Standard (mid-tier models)** | 12-16 GB | Detection + ReID concurrent, swap depth/segmentation |
| **Full (all large models concurrent)** | 20-24 GB | All models in memory |

Recommended minimum: **16 GB GPU** (RTX 4080 / T4 / A4000)

### 11.3 Processing Time Estimate (1-hour video, 1080p, 30fps = 108,000 frames)

**Key optimization: frame subsampling.** Not every frame needs full processing:
- Detection: process at **10 fps** (every 3rd frame) = 36,000 frames → sufficient for tracking
- ReID: compute only on **new detections and re-association events**, not every frame
- Depth/segmentation: 1-2 frames total (already specified)

| Phase | Time (RTX 4090 + TRT) | Time (T4 / 16GB) | Notes |
|-------|----------------------|-------------------|-------|
| Phase 0: Scene Profiling | 2-4 min | 4-8 min | Depth + segmentation + VLM calls |
| Phase 1: Tracking (10fps) | 8-15 min | 15-25 min | 36K frames × ~5ms det + ~2ms track |
| Phase 1: ReID extraction | 3-8 min | 5-12 min | ~2ms/crop, only on association events |
| Phase 2: Calibration | <1 min | <1 min | Math on tracking data |
| Phase 3: Zone Discovery | 3-5 min | 5-8 min | Clustering + VLM zone naming |
| Phase 4: Analytics + Safety | 2-3 min | 3-5 min | Math on tracking data |
| Phase 5-6: Validation + Export | 1-2 min | 1-2 min | |
| **Total** | **~20-35 min** | **~35-60 min** | |

**Note:** The 10fps subsampling is standard practice in CCTV analytics — people move slowly enough that 10fps captures all meaningful position changes. Frame skipping is configurable per scene (the Scene Profiler may increase to 15fps for fast-moving transit scenes or decrease to 5fps for parking lots).

### 11.4 VLM API Cost Per Video

| Component | Calls | Estimated Cost |
|-----------|-------|---------------|
| Scene Profiling | 2-3 | $0.01-0.03 |
| Zone Naming | N zones (~5-15) | $0.02-0.08 |
| **Total per video** | **7-18 calls** | **$0.03-0.11** |

At 1000 videos/day: $30-110/day for VLM calls.

---

## 12. What Changed From Current RetailVision

| Aspect | Current (RetailVision) | New (Universal CCTV Platform) |
|--------|----------------------|------------------------------|
| Input | Video + config + API keys | Video only |
| Environments | Indoor retail/food court | Any CCTV scenario (14+ environment types) |
| Calibration | Single method (person-height at 1.7m) | Multi-signal Bayesian fusion (GeoCalib + DA3 + person-height) |
| Detection | YOLOv11 (AGPL, NMS, people only) | RF-DETR (Apache 2.0, NMS-free, people + vehicles) |
| Tracking | BoTSORT (weak ReID, duplicates) | Fused detection-ReID-tracking with post-dedup |
| Scene understanding | VLM guesses from 1 frame | Depth + segmentation + VLM (3 signals) |
| Zone discovery | 3 hardcoded strategies + 6 rigid profiles | Structure-first + adaptive behavioral clustering |
| Zone taxonomy | 7 retail-specific types | Universal root categories + VLM-generated subtypes |
| Analytics | Retail-biased metrics | Universal metrics + scene-adapted interpretation rules |
| Safety | None | 3-tier (tracking-based + specialist models + segmentation masks) |
| Prompts | Hardcoded templates | VLM-generated, scene-adapted prompt context blocks |
| Strategy profiles | 6 hardcoded profiles | Dynamic — generated per scene by Scene Profiler |
| Confidence reporting | None | Every output carries confidence + degradation warnings |
| Edge case handling | None (assumes good conditions) | Explicit detection and handling of 15+ edge cases |
| Licensing | AGPL risk (YOLOv11) | Apache 2.0 core (RF-DETR, DA3, OSNet) |

---

## 13. Privacy & Compliance

### 13.1 EU AI Act Considerations
CCTV analytics is classified as **high-risk** under the EU AI Act (transparency rules effective August 2026):
- System must provide clear documentation of what data is processed and what decisions are made
- No real-time biometric identification (face recognition) — the platform uses body/silhouette tracking only
- Transparency: output reports must include methodology description accessible to non-technical users
- Data minimization: process only what's needed, don't store raw video frames beyond processing

### 13.2 Privacy-by-Design Architecture
- **No face detection or recognition** — detection uses body bounding boxes, ReID uses body/clothing appearance only
- **No PII in outputs** — reports contain zone analytics (aggregated counts, dwell times), not individual identity information
- **Track embeddings are ephemeral** — ReID embeddings are used during processing and discarded, not stored in output
- **Configurable anonymization** — optional face/body blurring for any visualizations that include camera frames
- **On-premise processing** — video data never leaves the processing machine unless user explicitly exports

### 13.3 Environment-Specific Privacy Notes
- **Hospitals/schools**: particularly sensitive — output must never contain enough information to re-identify individuals
- **Borders/perimeter**: government use cases may have different requirements — support configurable retention policies
- **Parking lots**: license plate detection is explicitly NOT included (out of scope, privacy risk)

---

## 14. Non-Goals & Constraints

- **No UI/dashboard changes** — existing demo system is sufficient
- **No deployment infrastructure changes** — current Cloudflare Tunnel + FastAPI + React remains
- **No real-time streaming** — batch processing only
- **No cross-camera tracking** — single camera per video file
- **No custom model training in MVP** — use pretrained models, fine-tuning is a future optimization
- **Tier 3 safety features are roadmap** — not shipped initially
- **Budget: minimize VLM API calls** — <20 calls per video

---

## 15. Success Criteria

1. **Zero-config**: Process a video from any of the 14 target environments without manual parameter tuning
2. **Auto-classification**: Correctly identify environment type in >85% of cases
3. **Calibration convergence**: Multi-signal fusion produces:
   - <20% metric error for "high confidence" scenes (well-lit indoor, 30+ tracked people)
   - <40% metric error for "medium confidence" scenes
   - Explicit "unable to calibrate reliably" for edge cases (overhead, IR, empty)
4. **Reduced duplicate detections**: NMS-free detection architecture significantly reduces (not eliminates) duplicate bounding boxes compared to current NMS-based approach. Note: does NOT eliminate ghost detections from reflections or false positives on screens/posters.
5. **Unique visitor accuracy**: System honestly reports ±15% margin; actual accuracy within ±15% of ground truth on labeled test videos with diverse-clothing scenes
6. **Safety Tier 1**: All tracking-based safety events detected with <10% false positive rate on standard-condition footage
7. **Graceful degradation**: System handles all documented edge cases without crashing or producing silently incorrect output — every degraded condition is flagged in the report
8. **Processing time**: <35 minutes for 1-hour 1080p video on RTX 4090; <60 minutes on T4/16GB GPU
9. **VLM cost**: <$0.20 per video (accounting for gates + retries, hard ceiling at 25 calls)

---

## 16. What Changed From Current RetailVision

(See comparison table in Section 12 above)

---

## Appendix A: Research References

- **RF-DETR**: ICLR 2026, Apache 2.0, github.com/roboflow/rf-detr
- **DA3-Metric**: Depth Anything V3, Apache 2.0, github.com/ByteDance-Seed/Depth-Anything-3
- **GeoCalib**: ECCV 2024, learned camera intrinsics from single image
- **Any-Resolution-Any-Geometry**: CVPR 2026, github.com/Dreamaker-MrC/Any-Resolution-Any-Geometry (optional for 4K+ cameras)
- **Depth Any Camera**: CVPR 2025, MIT license, handles fisheye/360 cameras
- **Grounded SAM 2**: Apache 2.0, github.com/IDEA-Research/Grounded-SAM-2
- **BoxMOT**: Multi-object tracking with pluggable ReID, github.com/mikel-brostrom/boxmot
- **OSNet**: Lightweight ReID, MIT license, 2.2M params
- **CLIP-ReID**: ViT-based ReID for person + vehicle, github.com/Syliz517/CLIP-ReID

## Appendix B: Datasets for Testing

- **MOT17/MOT20**: Multi-object tracking benchmarks
- **VIRAT**: Multi-site outdoor surveillance
- **UCF-Crime**: 1900 videos, 13 anomaly classes
- **ShanghaiTech**: 13 scenes, 270K+ frames (anomaly detection)
- **DanceTrack**: Complex multi-person tracking
- **CrowdHuman**: Dense crowd detection benchmark
- **PETS 2006**: Abandoned object detection benchmark
- **VeRi-776**: Vehicle re-identification
