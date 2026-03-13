# RetailVision Platform Architecture

> Agentic CCTV analytics platform: video in, interactive intelligence out.

---

## Table of Contents

1. [High-Level Design](#1-high-level-design)
2. [Platform Flow](#2-platform-flow)
3. [Module A: Video Pre-Processing & Tracking](#3-module-a-video-pre-processing--tracking)
4. [Module B: Zone Discovery Agent (26-Tool Pipeline)](#4-module-b-zone-discovery-agent-26-tool-pipeline)
5. [Module C: Chat API (ReAct Agentic VLM)](#5-module-c-chat-api-react-agentic-vlm)
6. [Module D: Frontend Dashboard](#6-module-d-frontend-dashboard)
7. [Models & Tools Reference](#7-models--tools-reference)
8. [Configuration Reference](#8-configuration-reference)
9. [Data Schemas](#9-data-schemas)
10. [Deployment Architecture](#10-deployment-architecture)

---

## 1. High-Level Design

RetailVision is an end-to-end agentic platform that transforms raw CCTV footage into interactive, AI-powered retail analytics. It operates as four loosely coupled modules:

```
                          RetailVision Platform
 ================================================================

  [CCTV Video]
       |
       v
 +---------------------+     +-----------------------------+
 |   MODULE A           |     |   MODULE B                   |
 |   Video Processing   |---->|   Zone Discovery Agent       |
 |                       |     |                               |
 |  YOLO11m + BoTSORT   |     |  26 Tools, 6 Phases           |
 |  Person detection     |     |  3 LLM Decision Gates         |
 |  Multi-object track   |     |  3 Zone Discovery Strategies  |
 |  Keyframe extraction  |     |  VLM enrichment (Qwen)        |
 |  Quality scoring      |     |  Depth analysis (DepthPro)    |
 |                       |     |                               |
 |  Output: SQLite DB    |     |  Output: report.json          |
 +---------------------+     +-----------------------------+
                                          |
                                          v
 +-----------------------------+     +-----------------------+
 |   MODULE C                   |     |   MODULE D             |
 |   Chat API Server            |<--->|   React Dashboard      |
 |                               |     |                         |
 |  FastAPI + SSE streaming     |     |  React 19 + Vite 6     |
 |  ReAct agentic loop          |     |  Tailwind CSS 4        |
 |  5 data query tools          |     |  10 visualization types|
 |  Max 5 reasoning turns       |     |  Three.js 3D BEV       |
 |  Qwen 3.5-9B (OpenRouter)   |     |  Supabase auth         |
 |  Supabase JWT auth           |     |  SSE real-time stream  |
 +--------------+---------------+     +-----------------------+
                |
                v
        [vision-ai.work]
        Cloudflare Tunnel
```

### Design Principles

- **Offline-first processing** - Tracking and zone discovery run fully offline; only VLM calls and auth require network
- **Agentic architecture** - Both the pipeline (Module B) and chat (Module C) use ReAct-style reasoning loops where an LLM decides what to do next
- **Separation of compute** - Heavy GPU work (YOLO) runs locally; VLM inference is routed through OpenRouter to leverage cloud models
- **Progressive data refinement** - Raw pixels -> detections -> tracks -> zones -> analytics -> natural language answers

---

## 2. Platform Flow

### End-to-End Pipeline

```
 CCTV Video (MP4)
    |
    |  Step 1: Detection & Tracking (local, GPU)
    |  - YOLO11m detects persons per frame
    |  - BoTSORT assigns persistent track IDs
    |  - Keyframes extracted every 150 frames
    |  - Track quality scored (0-1)
    |
    v
 SQLite Database
    |  (detections, keyframes, track_summaries, videos)
    |
    |  Step 2: Zone Discovery Agent (26 tools, VLM-driven)
    |  - Phase 1: Scene understanding + BEV calibration
    |  - GATE 1: LLM selects strategy profile
    |  - Phase 2: 3 zone discovery strategies -> fusion
    |  - GATE 2: LLM reviews zones, may retry
    |  - Phase 3: VLM enrichment (classify, describe, inventory)
    |  - GATE 3: LLM reviews classifications
    |  - Phase 4: Analytics (visits, dwell, flow, temporal)
    |  - Phase 5: Validation (silhouette, coverage, agreement)
    |  - Phase 6: Visualization & export
    |
    v
 report.json + visualizations
    |
    |  Step 3: Chat API serves interactive queries
    |  - Loads report.json at startup
    |  - ReAct loop: VLM reasons + calls data tools
    |  - Streams response via SSE
    |
    v
 React Dashboard (vision-ai.work)
    |  - Renders 10 visualization types
    |  - Interactive zone maps, 3D BEV, Sankey flows
    |  - Video playback with HTTP range requests
```

### Data Lifecycle

| Stage | Input | Processing | Output |
|-------|-------|-----------|--------|
| Tracking | MP4 video | YOLO11m + BoTSORT | SQLite (detections, keyframes, tracks) |
| Calibration | Reference keyframe | Person height -> BEV homography | H_bev matrix (pixel -> meters) |
| Zone Discovery | BEV tracks + dwell analysis | ST-DBSCAN, occupancy grid, trajectory graph | Zone candidates (polygons) |
| Fusion | 3 sets of candidates | Multi-strategy merge (overlap + consensus) | Fused zone registry |
| Enrichment | Zone crops + VLM | Object detection, signage OCR, classification | Annotated zones |
| Analytics | Tracks + zones | Visit counting, dwell stats, Markov flow | Per-zone metrics |
| Chat | User query + report.json | ReAct VLM + 5 data tools | Markdown + visualizations |

---

## 3. Module A: Video Pre-Processing & Tracking

### Architecture

```
 Video File
    |
    v
 +-----------------------------------------------------------+
 |  RetailTracker (tracker/detector.py)                       |
 |                                                             |
 |  +-----------+    +----------+    +---------+              |
 |  | YOLO11m   |--->| BoTSORT  |--->| SQLite  |              |
 |  | (person   |    | (multi-  |    | (batch  |              |
 |  |  detect)  |    |  object  |    |  insert |              |
 |  |           |    |  track)  |    |  2000)  |              |
 |  +-----------+    +----------+    +---------+              |
 |       |                                |                    |
 |       +--- Keyframe extraction --------+                    |
 |       |    (every 150 frames)                               |
 |       |                                                     |
 |       +--- Track quality scoring                            |
 |            (post-processing)                                |
 +-----------------------------------------------------------+
```

### Detection Model

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | `yolo11m.pt` (YOLOv11 Medium) | Good balance of speed and accuracy for 1080p CCTV |
| Input size | `1280` px | Higher resolution catches distant/small people in wide-angle CCTV |
| Confidence | `0.25` (pipeline) / `0.30` (default) | Low threshold for CCTV where people are often small and partially occluded |
| IoU threshold | `0.5` | Standard non-max suppression |
| Classes | `[0]` (person only) | Retail analytics focuses on people |
| Framework | UltraLytics | Industry-standard YOLO implementation |

### Tracker (BoTSORT)

Configuration from `tracker/botsort_retail.yaml`:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `tracker_type` | `botsort` | State-of-the-art MOT with ReID support |
| `track_high_thresh` | `0.25` | Matches detection confidence for CCTV |
| `track_low_thresh` | `0.1` | Catches marginal detections to maintain tracks |
| `new_track_thresh` | `0.25` | Prevents spurious new tracks from noise |
| `track_buffer` | `90` frames | 3 seconds at 30fps — handles temporary occlusions (people behind pillars, shelves) |
| `match_thresh` | `0.8` | Strict appearance matching |
| `fuse_score` | `true` | Combines appearance + IoU for robust matching |
| `with_reid` | `true` | ReID features preserve identity across occlusions |
| `gmc_method` | `sparseOptFlow` | Minimal compute for fixed CCTV cameras (no global motion) |
| `proximity_thresh` | `0.5` | Spatial proximity for association |
| `appearance_thresh` | `0.25` | Appearance similarity threshold |

### Track Quality Scoring

Post-processing assigns a quality score (0-1) to each track:

```
quality = 0.25 * duration_norm      (min(duration/30s, 1))
        + 0.20 * count_norm         (min(detections/50, 1))
        + 0.20 * avg_confidence
        + 0.15 * completeness       (detections / duration_frames)
        + 0.20 * smoothness         (1 - std(displacements) / mean(displacements))
```

Tracks with quality < `0.3` are filtered out by the agent pipeline.

### Database Schema (SQLite)

```sql
videos        -- Video metadata: fps, resolution, duration, frame count
detections    -- Per-frame per-person: frame_idx, track_id, bbox, confidence, x/y center
keyframes     -- JPEG-encoded frames extracted every N frames for VLM analysis
track_summaries -- Aggregated per-track: duration, detection count, avg confidence, quality
```

### CLI Usage

```bash
# Full pipeline: tracking + zone discovery
python -m scripts.process_video \
  --video "path/to/video.mp4" \
  --minutes 30 \
  --output output/real \
  --conf 0.30 --imgsz 1280 \
  --openrouter-key $OPENROUTER_API_KEY

# Tracking only
python -m scripts.run_tracker \
  --video "path/to/video.mp4" \
  --db data/tracks.db \
  --conf 0.25 --imgsz 1280
```

---

## 4. Module B: Zone Discovery Agent (26-Tool Pipeline)

### Architecture Overview

The Zone Discovery Agent is a **hybrid ReAct orchestrator** — it runs fixed tool phases sequentially, but 3 LLM decision gates between phases dynamically control strategy selection, parameter tuning, and quality validation.

```
 +===================================================================+
 |                    Zone Discovery Agent                            |
 |                                                                     |
 |  Phase 1: Scene Understanding (6 tools, always runs)               |
 |    ingest_from_db -> extract_reference_frame -> calibrate ->       |
 |    classify_scene_type -> vlm_scene_layout -> depth_analysis       |
 |                                                                     |
 |  ======================== GATE 1 ================================  |
 |  LLM analyzes scene -> selects strategy profile -> sets params     |
 |  (6 profiles: general, pedestrian_indoor, pedestrian_outdoor,      |
 |   high_traffic, sparse_activity, monitored_perimeter)              |
 |  ================================================================  |
 |                                                                     |
 |  Phase 2: Zone Discovery (6-8 tools, LLM-selected)                |
 |    compute_dwell_points -> strategy_A (dwell clustering) ->        |
 |    strategy_B (occupancy grid) -> strategy_C (trajectory graph) -> |
 |    fuse_zone_candidates -> vlm_detect_structures                   |
 |                                                                     |
 |  ======================== GATE 2 ================================  |
 |  LLM reviews discovered zones -> may trigger Phase 2 re-run       |
 |  with relaxed parameters                                           |
 |  ================================================================  |
 |                                                                     |
 |  Phase 3a: Quick Analytics (2 tools)                               |
 |    crop_zone_images -> compute_quick_zone_analytics                |
 |                                                                     |
 |  Phase 3b: Zone Enrichment (5-7 tools, LLM-selected)              |
 |    depth_zone_analysis -> segment_zone_refinement ->               |
 |    vlm_object_inventory -> vlm_signage_reader ->                   |
 |    vlm_zone_classifier -> vlm_zone_describer                       |
 |                                                                     |
 |  Phase 3c: Merge Registry (1 tool)                                 |
 |    merge_zone_registry                                             |
 |                                                                     |
 |  ======================== GATE 3 ================================  |
 |  LLM reviews zone classifications -> may reclassify               |
 |  ================================================================  |
 |                                                                     |
 |  Phase 4: Analytics (4 tools, always runs)                         |
 |    compute_zone_analytics -> compute_flow_analytics ->             |
 |    compute_temporal_analytics -> compute_spatial_analytics          |
 |                                                                     |
 |  Phase 5: Validation (2 tools, always runs)                        |
 |    validate_zones -> quality_gate                                   |
 |    (quality_gate may trigger full Phase 2-5 retry)                 |
 |                                                                     |
 |  Phase 6: Visualization & Export (4 tools, always runs)            |
 |    plan_visualizations -> render_all_visualizations ->             |
 |    render_3d_scene -> export_dashboard_bundle                       |
 +===================================================================+
```

### Phase 1: Scene Understanding

| Tool | Purpose | Key Details |
|------|---------|-------------|
| `ingest_from_db` | Load tracking data from SQLite | Filters tracks by quality threshold (0.3), converts to DataFrame |
| `extract_reference_frame` | Get mid-video keyframe | Used for VLM scene analysis and calibration |
| `calibrate_from_person_height` | Compute BEV transformation | Uses 1.7m person height assumption to derive pixel-to-meter homography |
| `classify_scene_type` | VLM classifies the scene | Qwen analyzes frame -> retail, food court, mall, etc. |
| `vlm_scene_layout` | VLM describes spatial layout | Identifies fixed structures, walkways, areas |
| `depth_scene_analysis` | Monocular depth estimation | Optional, uses Depth Pro via Replicate API |

### Phase 2: Zone Discovery Strategies

Three independent strategies discover zone candidates, then fusion merges them:

**Strategy A — Dwell Clustering:**
1. Identifies "dwell points" where people slow below 0.5 m/s for >10 seconds within 2m radius
2. Runs ST-DBSCAN (spatial eps: 2.0m, temporal eps: 60s, min samples: 5)
3. Builds convex hull polygons around clusters

**Strategy B — Occupancy Grid:**
1. Divides BEV space into 0.5m grid cells
2. Counts time-weighted occupancy per cell
3. Thresholds cells at 0.1 density
4. DBSCAN clusters dense cells into zones

**Strategy C — Trajectory Graph:**
1. Discretizes BEV space at 0.3m resolution
2. Builds a weighted graph of movement between cells
3. Identifies high-traffic nodes (edge weight > 3)
4. Clusters connected components into zones

**Fusion:**
- Merges candidates from all strategies
- Requires consensus from >= 2 strategies (configurable)
- Merges overlapping zones within 4.0m, area threshold 2.5m^2
- Maximum zone area cap: 50.0m^2

### Phase 3: Zone Enrichment

| Tool | Purpose | VLM/Model Used |
|------|---------|---------------|
| `crop_zone_images` | Extract zone region from reference frame | OpenCV |
| `depth_zone_analysis` | Per-zone depth estimation | Depth Pro (Replicate) |
| `segment_zone_refinement` | Semantic segmentation cleanup | Morphological ops + watershed |
| `vlm_object_inventory` | Identify objects in zone | Qwen 3.5-35B |
| `vlm_signage_reader` | OCR text from signs in zone | Qwen 3.5-35B |
| `vlm_zone_classifier` | Assign zone type (cafe, shop, etc.) | Qwen 3.5-35B |
| `vlm_zone_describer` | Generate natural language description | Qwen 3.5-35B |

### Phase 4: Analytics Computation

| Tool | Metrics Computed |
|------|-----------------|
| `compute_zone_analytics` | total_visits, unique_visitors, avg/median/p95 dwell seconds, peak_hour, avg/max occupancy, return_rate, density |
| `compute_flow_analytics` | Zone-to-zone transitions, counts, probabilities (Markov chain) |
| `compute_temporal_analytics` | Hourly visit patterns, rush hour detection (2x average threshold), 5-minute temporal bins |
| `compute_spatial_analytics` | Density heatmaps (0.5m cells), spatial gradients |

### Phase 5: Validation

| Metric | Description |
|--------|-------------|
| Silhouette score | Spatial clustering quality of zones |
| Coverage | Percentage of tracked activity falling within discovered zones |
| VLM agreement | How well VLM classifications match behavioral data |
| Count sanity | Whether zone metrics are internally consistent |
| Multi-strategy | Percentage of zones confirmed by multiple discovery strategies |
| **Overall threshold** | **0.40** — below this triggers a Phase 2-5 retry |

### Quality Gate Retry

When the quality gate fails, up to 2 retries with relaxed parameters:
- `stdbscan_spatial_eps_m *= 1.3` (wider spatial clustering)
- `min_dwell_seconds *= 0.8` (shorter dwell threshold)
- `fusion_min_strategies = 1` (accept single-strategy zones)

### Strategy Profiles

Gate 1 selects one of 6 profiles based on scene analysis:

| Profile | Scene Type | Key Differences |
|---------|-----------|-----------------|
| `general` | Default | All 3 strategies + full enrichment (depth, segmentation, signage) |
| `pedestrian_indoor` | Malls, offices, hospitals | Same as general (indoor scenes need full analysis) |
| `pedestrian_outdoor` | Markets, plazas, parks | Drops dwell clustering (outdoor dwell is less meaningful) |
| `high_traffic` | Corridors, stations | Focuses on occupancy + trajectory; skips structure detection |
| `sparse_activity` | Warehouses, parking | Drops trajectory graph (too few paths); adds segmentation |
| `monitored_perimeter` | Gates, checkpoints | Minimal: occupancy grid + structure detection only |

---

## 5. Module C: Chat API (ReAct Agentic VLM)

### Architecture

```
 User Query
    |
    v
 +---------------------------------------------------------------+
 |  FastAPI Server (api/chat_server.py)                           |
 |                                                                 |
 |  Supabase JWT Auth Gate (Bearer token, @ipsotek.com domain)   |
 |                                                                 |
 |  +-----------------------------------------------------------+ |
 |  |  ReAct Agentic Loop (max 5 turns)                          | |
 |  |                                                             | |
 |  |  Turn 1: VLM reasons about query                           | |
 |  |    -> Returns {action: "query_zones", action_input: {...}}  | |
 |  |                                                             | |
 |  |  Turn 2: Tool result injected back                         | |
 |  |    -> VLM analyzes data, may call another tool or...       | |
 |  |    -> Returns {action: "final_answer", text: "...",        | |
 |  |               visualizations: [...], actions: [...]}       | |
 |  |                                                             | |
 |  |  (Max 5 turns, last turn forces final_answer)              | |
 |  +-----------------------------------------------------------+ |
 |                                                                 |
 |  SSE Stream: session_id -> text -> visualizations -> [DONE]    |
 +---------------------------------------------------------------+
```

### VLM Configuration (Chat)

| Parameter | Value |
|-----------|-------|
| Model | `qwen/qwen3.5-9b` (via OpenRouter) |
| Temperature | `0.3` |
| Max tokens | `4096` |
| Max agent turns | `5` |
| JSON parsing | Strips `<think>` tags, code fences, extracts brace blocks |

### Data Tools (5 tools available to VLM)

| Tool | Purpose | Parameters |
|------|---------|-----------|
| `query_zones` | Sort, filter, rank zones | `sort_by`, `order`, `limit`, `zone_type` |
| `get_zone_detail` | Full detail for one zone | `zone_id` |
| `search_zones` | Name-based zone lookup | `query` |
| `get_flow_data` | Customer flow transitions | `zone_id` (optional filter) |
| `get_summary_stats` | Aggregate overview | (none) |

### Supported Metrics

```
total_visits, unique_visitors, avg_dwell_seconds, median_dwell_seconds,
p95_dwell_seconds, peak_hour, avg_occupancy, max_occupancy,
return_rate, density_people_per_m2_hr, area_m2
```

### Response Format

The VLM produces structured JSON with:
- **text** — Markdown answer with actual data values
- **visualizations** — Array of typed viz objects (zone_map, bar_chart, etc.)
- **actions** — UI commands (set_theme, set_viz_size)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (no auth) |
| `/api/report` | GET | Full report.json |
| `/api/video` | GET | Video stream with HTTP Range support |
| `/api/chat` | POST | Chat with SSE streaming response |

### SSE Event Sequence

```
data: {"session_id": "abc123"}
data: {"type": "text", "content": "The busiest zone is..."}
data: {"type": "visualization", "visualization": {"type": "bar_chart", ...}}
data: {"type": "visualization", "visualization": {"type": "zone_map", ...}}
data: {"type": "action", "action": {"type": "set_theme", "value": "dark"}}
data: [DONE]
```

---

## 6. Module D: Frontend Dashboard

### Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19 | UI framework |
| Vite | 6.2 | Build tool + HMR dev server |
| Tailwind CSS | 4 | Utility-first styling |
| Three.js | 0.172 | 3D bird's-eye-view scene |
| @react-three/fiber | 9 | React Three.js bindings |
| @react-three/drei | 10 | Three.js helpers |
| Recharts | 2.15 | Bar/line/area charts |
| D3 | 3.x | Sankey diagrams, scales, shapes |
| Framer Motion | 12 | Animations and transitions |
| Supabase JS | 2.99 | Authentication client |
| Lucide React | 0.474 | Icon library |
| React Router | 7.13 | Client-side routing |

### Page Structure

```
 /login          -> LoginPage.jsx        (Supabase email/password auth)
 /set-password   -> SetPasswordPage.jsx  (Password reset flow)
 /               -> DashboardPage.jsx    (Analytics overview)
 /chat           -> ChatPage.jsx         (Agentic chat interface)
```

### 10 Visualization Types

| Type | Component | Description |
|------|-----------|-------------|
| `zone_map` | ZoneMapCard | Interactive Canvas zone map with click-to-inspect |
| `zone_map_bev` | ZoneMapBEVCard | Bird's-eye view zone layout |
| `zone_detail` | ZoneDetailCard | Deep dive into a single zone |
| `bar_chart` | BarChartCard | Rankings and comparisons (Recharts) |
| `sankey` | SankeyCard | Customer flow between zones (D3 Sankey) |
| `temporal` | TemporalCard | Hourly visit heatmap |
| `kpi_cards` | KPICard | Summary metric cards |
| `data_table` | DataTableCard | Tabular data with sorting |
| `heatmap_image` | HeatmapImageCard | Density heatmap overlay |
| `video_player` | VideoPlayerCard | CCTV footage playback via `/api/video` |

### UI Features

- **Dark/light theme** — switchable via chat command or UI toggle, persisted in localStorage
- **Visualization sizing** — compact / default / large modes
- **SSE streaming** — real-time message rendering as VLM generates response
- **Lazy loading** — all viz cards are code-split with `React.lazy()`
- **Suggested prompts** — PromptShowcase component offers starter queries

---

## 7. Models & Tools Reference

### AI Models Used

| Model | Where Used | Purpose | Provider |
|-------|-----------|---------|----------|
| **YOLOv11 Medium** (`yolo11m.pt`) | Module A: Tracker | Person detection in video frames | Local (UltraLytics) |
| **BoTSORT** (built into UltraLytics) | Module A: Tracker | Multi-object tracking with ReID | Local |
| **Qwen 3.5-35B** (`qwen/qwen3.5-35b-a3b`) | Module B: Pipeline | Primary VLM for scene analysis, zone classification, object inventory, signage reading | OpenRouter |
| **Qwen 2.5-VL-7B** (`qwen/qwen2.5-vl-7b-instruct`) | Module B: Pipeline | Fallback VLM when primary fails or rate-limited | OpenRouter |
| **Qwen 3.5-9B** (`qwen/qwen3.5-9b`) | Module C: Chat | Chat reasoning + tool calling | OpenRouter |
| **Depth Pro** | Module B: Pipeline (optional) | Monocular depth estimation for scene and zone analysis | Replicate |

### External Services

| Service | Purpose |
|---------|---------|
| **OpenRouter** | VLM API gateway (routes to Qwen models) |
| **Replicate** | Depth Pro model hosting (optional) |
| **Supabase** | User authentication (JWT, email/password) |
| **Cloudflare Tunnel** | Secure tunnel from localhost to vision-ai.work |

### Complete Tool Inventory

#### Module B: Zone Discovery Agent (26 tools + 3 gates)

**Phase 1 — Scene Understanding (6 tools):**

| # | Tool | Input | Output |
|---|------|-------|--------|
| 1 | `ingest_from_db` | SQLite DB, video_id | DataFrame of filtered tracks |
| 2 | `extract_reference_frame` | Keyframes table | Mid-video reference frame |
| 3 | `calibrate_from_person_height` | Reference frame, detections | H_bev homography matrix |
| 4 | `classify_scene_type` | Reference frame | Scene type label |
| 5 | `vlm_scene_layout` | Reference frame | Spatial layout description |
| 6 | `depth_scene_analysis` | Reference frame | Depth map (optional) |

**Phase 2 — Zone Discovery (6-8 tools, dynamic):**

| # | Tool | Input | Output |
|---|------|-------|--------|
| 7 | `compute_dwell_points` | BEV tracks | List of dwell events (location, duration) |
| 8 | `strategy_dwell_clustering` | Dwell points | Zone candidates (convex hull polygons) |
| 9 | `strategy_occupancy_grid` | BEV tracks | Zone candidates (density clusters) |
| 10 | `strategy_trajectory_graph` | BEV tracks | Zone candidates (graph components) |
| 11 | `fuse_zone_candidates` | All candidates A/B/C | Merged zone registry |
| 12 | `vlm_detect_structures` | Reference frame | Fixed structure zones (shelves, registers) |

**Phase 3 — Enrichment (8 tools, dynamic):**

| # | Tool | Input | Output |
|---|------|-------|--------|
| 13 | `crop_zone_images` | Reference frame, zone polygons | Cropped zone images |
| 14 | `depth_zone_analysis` | Zone crops | Per-zone depth info |
| 15 | `segment_zone_refinement` | Zone crops | Refined zone boundaries |
| 16 | `vlm_object_inventory` | Zone crops | Object lists per zone |
| 17 | `vlm_signage_reader` | Zone crops | OCR text from signs |
| 18 | `vlm_zone_classifier` | Zone crops + analytics | Zone type labels |
| 19 | `vlm_zone_describer` | Zone metadata | Natural language descriptions |
| 20 | `merge_zone_registry` | Enriched zones | Final consolidated registry |

**Phase 4 — Analytics (4 tools):**

| # | Tool | Input | Output |
|---|------|-------|--------|
| 21 | `compute_zone_analytics` | Tracks + zones | Visit counts, dwell stats, occupancy |
| 22 | `compute_flow_analytics` | Track sequences + zones | Transition matrix, probabilities |
| 23 | `compute_temporal_analytics` | Tracks + zones | Hourly patterns, rush hours |
| 24 | `compute_spatial_analytics` | Tracks | Density heatmaps |

**Phase 5 — Validation (2 tools):**

| # | Tool | Input | Output |
|---|------|-------|--------|
| 25 | `validate_zones` | Zone registry | Silhouette, coverage, agreement scores |
| 26 | `quality_gate` | Validation metrics | Pass/fail + retry decision |

**Phase 6 — Visualization (4 tools):**

| # | Tool | Input | Output |
|---|------|-------|--------|
| 27 | `plan_visualizations` | Zone registry, analytics | Visualization plan |
| 28 | `render_all_visualizations` | Zone registry, analytics | PNG images |
| 29 | `render_3d_scene` | Zone registry, BEV data | Three.js scene data |
| 30 | `export_dashboard_bundle` | Everything | report.json + assets |

**Decision Gates (3):**

| Gate | Between | Decision |
|------|---------|----------|
| GATE 1 | Phase 1 -> 2 | Selects strategy profile, tunes parameters |
| GATE 2 | Phase 2 -> 3 | Reviews zone quality, may trigger Phase 2 re-run |
| GATE 3 | Phase 3 -> 4 | Reviews zone classifications, may reclassify |

#### Module C: Chat API (5 tools)

| Tool | Purpose |
|------|---------|
| `query_zones` | Sort, filter, rank zones by any metric |
| `get_zone_detail` | Full metadata for a specific zone |
| `search_zones` | Name-based fuzzy search |
| `get_flow_data` | Customer movement transitions |
| `get_summary_stats` | Aggregate statistics |

---

## 8. Configuration Reference

### Pipeline Configuration (`agent/config.py`)

```
# Calibration
bev_resolution:          0.05 m/px     BEV pixel resolution
person_height_m:         1.7 m         Assumed person height for calibration

# VLM
vlm_primary_model:       qwen/qwen3.5-35b-a3b
vlm_fallback_model:      qwen/qwen2.5-vl-7b-instruct
vlm_temperature:         0.2
vlm_max_retries:         3
vlm_confidence_threshold: 0.5

# Zone Discovery - Dwell Analysis
dwell_speed_threshold_m_s: 0.5 m/s     Below this = dwelling
min_dwell_seconds:         10.0 s       Minimum dwell duration
confinement_radius_m:      2.0 m        Max radius for dwell event

# ST-DBSCAN Clustering
stdbscan_spatial_eps_m:    2.0 m        Spatial neighborhood radius
stdbscan_temporal_eps_s:   60.0 s       Temporal neighborhood window
stdbscan_min_samples:      5            Minimum cluster size

# Occupancy Grid
occupancy_grid_cell_m:     0.5 m        Grid cell size
occupancy_min_density:     0.1          Minimum density threshold

# Trajectory Graph
traj_edge_weight_threshold: 3           Minimum edge weight
traj_resolution:            0.3 m       Graph node resolution

# Fusion
fusion_min_strategies:     2            Min strategies to confirm zone
merge_threshold_m2:        2.5 m^2      Area overlap for merge
merge_max_distance_m:      4.0 m        Max distance for merge
max_zone_area_m2:          50.0 m^2     Upper area cap per zone

# Quality
quality_threshold:         0.40         Overall validation threshold
track_quality_threshold:   0.3          Min track quality for pipeline

# Temporal
temporal_bin_seconds:      300 (5 min)  Temporal aggregation bin
rush_multiplier:           2.0          Threshold = 2x avg for rush hour

# Retry
max_phase2_retries:        2            Max quality-gate retries
```

### Tracker Configuration (`tracker/botsort_retail.yaml`)

```
tracker_type:     botsort
track_high_thresh: 0.25        High-quality detection threshold
track_low_thresh:  0.1         Low-quality detection threshold
new_track_thresh:  0.25        New track initialization threshold
track_buffer:      90          Frames to keep lost tracks (3s @ 30fps)
match_thresh:      0.8         IoU matching threshold
fuse_score:        true        Fuse appearance + IoU scores
with_reid:         true        Enable ReID features
gmc_method:        sparseOptFlow  Camera motion compensation
proximity_thresh:  0.5         Spatial proximity threshold
appearance_thresh: 0.25        Appearance similarity threshold
```

---

## 9. Data Schemas

### report.json (Module B output / Module C input)

```json
{
  "meta": {
    "video_id": "55748ef61510",
    "scene_type": "indoor_food_court",
    "duration_seconds": 1800,
    "duration_min": 30
  },
  "zones": {
    "zone_001": {
      "zone_id": "zone_001",
      "business_name": "Central Cafe",
      "zone_type": "cafe",
      "description": "VLM-generated natural language description",
      "area_m2": 15.5,
      "polygon_bev": [[x, y], ...],
      "polygon_pixel": [[x, y], ...],
      "centroid_bev": [x, y],
      "bbox_pixel": [x1, y1, x2, y2],
      "vlm_confidence": 0.92,
      "objects": ["table", "chair", "menu_board"],
      "signage": {"detected": true, "text": ["CAFE"]},
      "depth_info": {...},
      "strategy_agreement": 3,
      "contributing_strategies": ["A", "B", "C"]
    }
  },
  "analytics": {
    "zone_001": {
      "total_visits": 245,
      "unique_visitors": 128,
      "avg_dwell_seconds": 45.3,
      "median_dwell_seconds": 38.0,
      "p95_dwell_seconds": 120.0,
      "peak_hour": 14,
      "avg_occupancy": 2.3,
      "max_occupancy": 8,
      "return_rate": 0.25,
      "density_people_per_m2_hr": 16.2
    }
  },
  "flow": {
    "transitions": [
      {"from_zone": "zone_001", "to_zone": "zone_003", "count": 45, "probability": 0.18}
    ],
    "top_paths": [...]
  }
}
```

### SQLite Schema (Module A output / Module B input)

```sql
CREATE TABLE videos (
    video_id TEXT PRIMARY KEY,
    path TEXT, fps REAL, total_frames INTEGER,
    width INTEGER, height INTEGER
);

CREATE TABLE detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT, frame_idx INTEGER, timestamp REAL,
    track_id INTEGER, x_center REAL, y_center REAL,
    bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL,
    bbox_w REAL, bbox_h REAL, confidence REAL, object_class TEXT
);

CREATE TABLE keyframes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT, frame_idx INTEGER, image BLOB
);

CREATE TABLE track_summaries (
    video_id TEXT, track_id INTEGER,
    first_frame INTEGER, last_frame INTEGER,
    duration_frames INTEGER, duration_seconds REAL,
    num_detections INTEGER, avg_confidence REAL,
    quality_score REAL,
    PRIMARY KEY (video_id, track_id)
);
```

---

## 10. Deployment Architecture

### Current Setup

```
 Internet
    |
    v
 [vision-ai.work]  <-- Cloudflare Tunnel (QUIC)
    |
    v
 [localhost:8100]   <-- FastAPI (Uvicorn)
    |                     |-- /api/*  (chat, report, video, health)
    |                     |-- /*      (SPA: dashboard/dist/index.html)
    |
    +-- OpenRouter API    (VLM inference: Qwen models)
    +-- Supabase          (JWT auth verification)
    +-- Replicate API     (Depth Pro, optional)
```

### Running the Stack

```bash
# 1. Start backend (serves API + built frontend)
PYTHONPATH=. python scripts/run_chat_server.py \
  --static-dir dashboard/dist \
  --port 8100

# 2. Start Cloudflare tunnel
cloudflared tunnel run vision-ai

# 3. (Development only) Start Vite dev server with HMR
cd dashboard && npm run dev   # localhost:5173
```

### Environment Variables

```
OPENROUTER_API_KEY     # Required for chat + pipeline VLM calls
REPLICATE_API_TOKEN    # Optional, for Depth Pro analysis
SUPABASE_URL           # Auth verification endpoint
SUPABASE_ANON_KEY      # Supabase anonymous key
```
