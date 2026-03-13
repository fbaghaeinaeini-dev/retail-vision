# Deep Research: Cutting-Edge Technologies for Universal Zero-Config CCTV Analytics (2025-2026)

**Research Date: March 2026**

---

## Table of Contents
1. [Person Detection & Tracking Models](#1-person-detection--tracking-models)
2. [Vision-Language Models for Scene Understanding](#2-vision-language-models-for-scene-understanding)
3. [Automatic Camera Calibration](#3-automatic-camera-calibration)
4. [Open CCTV Datasets](#4-open-cctv-datasets)
5. [Edge Deployment & Model Optimization](#5-edge-deployment--model-optimization)
6. [Zero-Configuration & Self-Adaptive Systems](#6-zero-configuration--self-adaptive-systems)
7. [Privacy-Preserving Analytics](#7-privacy-preserving-analytics)
8. [Competitive Landscape](#8-competitive-landscape)
9. [Emerging Paradigms](#9-emerging-paradigms)
10. [Action Recognition & Behavior Analysis](#10-action-recognition--behavior-analysis)
11. [Strategic Recommendations](#11-strategic-recommendations)

---

## 1. Person Detection & Tracking Models

### 1.1 Detection Models: The Current Hierarchy (March 2026)

#### YOLO26 (September 2025 / January 2026) — RECOMMENDED
- **Architecture**: Native end-to-end NMS-free detection; eliminates Distribution Focal Loss (DFL) for streamlined exports
- **Key innovations**: ProgLoss, Small-Target-Aware Label Assignment (STAL), MuSGD optimizer (hybrid of SGD + Muon, inspired by Kimi K2 LLM training)
- **Performance**: Up to 43% faster on CPUs; 56.7% mAP50-95 (X variant, oriented detection)
- **Tasks**: Detection, segmentation, classification, pose estimation, oriented object detection
- **Variants**: Nano, Small, Medium, Large, Extra-Large
- **Export**: ONNX, TensorRT, CoreML, TFLite; INT8/FP16 quantization with minimal accuracy impact
- **License**: AGPL-3.0 (Ultralytics) — requires commercial license for proprietary use
- **Source**: [Ultralytics YOLO26 Docs](https://docs.ultralytics.com/models/yolo26/) | [arXiv Paper](https://arxiv.org/abs/2509.25164)

#### YOLOv12 (February 2025)
- **Architecture**: First attention-centric YOLO — departs from pure CNN, uses attention mechanisms while retaining real-time speed
- **Performance**: YOLOv12-N: 40.5% mAP @ 1.62ms (T4 GPU); outperforms YOLO11-N by 1.1% mAP; YOLOv12-X beats RT-DETRv2/v3
- **Significance**: Proved that attention mechanisms can work in real-time detection
- **Source**: [OpenReview](https://openreview.net/forum?id=gCvByDI4FN) | [Ultralytics Docs](https://docs.ultralytics.com/models/yolo12/)

#### RF-DETR (March 2025) — RECOMMENDED FOR ACCURACY-CRITICAL TASKS
- **Architecture**: Real-time transformer detector using DINOv2 backbone + Neural Architecture Search (NAS)
- **Performance**: First real-time detector to exceed 60 AP on COCO; RF-DETR-nano: 48.0 AP (beats D-FINE-nano by 5.3 AP); Base: 53.3 mAP; 6.0ms/img on T4
- **Standout**: 86.7 mAP on RF100-VL (domain adaptation benchmark) — exceptional generalization
- **License**: Apache 2.0 (commercial-friendly)
- **Source**: [GitHub (Roboflow)](https://github.com/roboflow/rf-detr) | [arXiv](https://arxiv.org/abs/2511.09554)

#### D-FINE (ICLR 2025 Spotlight)
- **Architecture**: Fine-grained Distribution Refinement (FDR) + Global Optimal Localization Self-Distillation (GO-LSD)
- **Performance**: D-FINE-L: 54.0% AP @ 124 FPS (T4); D-FINE-X: 55.8% AP @ 78 FPS; with Objects365 pretraining: up to 59.3% AP
- **Strength**: Excellent in dense crowds, backlighting, motion blur
- **License**: Apache 2.0
- **Source**: [GitHub](https://github.com/Peterande/D-FINE)

#### Detection Model Recommendation for CCTV Analytics
| Use Case | Recommended Model | Rationale |
|---|---|---|
| Real-time edge deployment | YOLO26-S/M | Best speed-accuracy balance, NMS-free, quantization-friendly |
| Maximum accuracy (batch) | RF-DETR-2XL or D-FINE-X | Highest AP, transformer architecture, strong generalization |
| Diverse camera types | RF-DETR | Best domain adaptation (RF100-VL benchmark) |
| Small object detection | YOLO26 (with STAL) | Purpose-built small-target assignment |

### 1.2 Challenging Conditions: Night, Rain, Fog, Thermal, Fisheye

- **Thermal/night vision**: YOLO11 and YOLOv8 trained on thermal facial databases achieve strong detection. Enhanced Tiny-YOLOv3 achieves 90% accuracy for night pedestrian detection at 4.48ms. Models trained on LWIR (Long-Wave Infrared) achieve 95%+ precision at 30 FPS.
- **Fisheye lenses**: YOLO-fastest-xl combined with fisheye cameras achieves good accuracy for in-cabin detection. OpenCV fisheye correction + standard detectors is the practical approach.
- **Fog/rain**: No specific breakthrough models — the best approach is domain adaptation via fine-tuning on degraded imagery, or using image restoration preprocessing.
- **Practical recommendation**: Train on mixed-domain data (RGB + thermal + degraded). Use RF-DETR for its superior domain adaptation score.

### 1.3 Multi-Object Tracking: State of the Art

#### Current SOTA Trackers (2025-2026)

| Tracker | Key Metric | Innovation |
|---|---|---|
| **BoT-SORT / BoT-SORT-ReID** | 80.5 MOTA, 80.2 IDF1, 65.0 HOTA (MOT17) | Camera motion compensation + ReID |
| **CAMELTrack** (2025) | +3.2% HOTA over prior SOTA | Context-Aware Multi-cue Exploitation |
| **MATR** | 71.3 HOTA (DanceTrack) | With supplementary data |
| **RAMA** | 75.0% IDF1 (MOT16) | Re-identification assistance + multi-stage association |
| **Deep OC-SORT** | Strong occlusion handling | Dynamic visual appearance + camera motion compensation |

#### Key Tracking Advances
- **Re-identification across occlusions**: RAMA introduces separately trained pedestrian ReID models for discriminative feature extraction
- **Motion-Aware Tracking (MAT)**: Integrates motion localization for camera and non-rigid object movement; dynamic reconnection context for long-range reconnections
- **NvDeepSORT/NvDCF (NVIDIA)**: DeepStream SDK 6.2+ supports ReID model integration for improved long-term association
- **End-to-end transformers**: Emerging trend — attention-based trackers that jointly detect and track without explicit association

#### Tracking Recommendation for CCTV
- **Primary**: BoT-SORT-ReID with YOLO26 detector — proven, well-documented, strong ReID
- **For occlusion-heavy scenes**: Deep OC-SORT or RAMA
- **For NVIDIA edge deployment**: NvDCF with ReID model in DeepStream pipeline
- **For batch processing**: Can afford heavier trackers; use CAMELTrack or MATR-style approaches

### 1.4 Pose Estimation Models

| Model | Performance | Speed | Use Case |
|---|---|---|---|
| **YOLO26-Pose** | Competitive on COCO | Real-time on edge | Integrated with detection pipeline |
| **RTMPose-m** | 75.8% AP (COCO) | 90+ FPS (CPU), 430+ FPS (GPU) | Best speed-accuracy balance |
| **RTMPose-s** | 72.2% AP (COCO) | 70+ FPS (Snapdragon 865) | Mobile/edge |
| **ViTPose++** | SOTA accuracy (COCO) | Slower | Maximum accuracy |
| **RTMW** | Whole-body (face+hands+body) | Real-time | Comprehensive pose |

- **rtmlib**: Super lightweight library for RTMPose/ViTPose WITHOUT mmcv, mmpose, mmdet dependencies — ideal for deployment
- **Recommendation**: RTMPose for privacy-preserving analytics (pose skeleton instead of face); YOLO26-Pose for integrated pipeline

---

## 2. Vision-Language Models for Scene Understanding

### 2.1 Top VLMs for CCTV Analytics (Ranked)

#### Qwen3-VL (September-October 2025) — TOP RECOMMENDATION
- **Architecture**: Dense (2B/4B/8B/32B) and MoE (30B-A3B/235B-A22B) variants
- **Video capabilities**: 256K-token native context (expandable to 1M); processes hours-long videos with second-level temporal indexing; Interleaved-MRoPE for spatial-temporal modeling
- **Key features**: DeepStack integration, text-based time alignment for precise temporal grounding, GUI agent capability, visual code generation, advanced spatial perception (object positions, viewpoints, occlusions)
- **License**: Apache 2.0
- **Source**: [GitHub](https://github.com/QwenLM/Qwen3-VL) | [arXiv](https://arxiv.org/abs/2511.21631)

#### InternVL3.5 (August 2025)
- **Architecture**: ViT-MLP-LLM paradigm; InternViT-300M/6B vision encoder; Qwen3/GPT-OSS language backbone
- **Performance**: Up to +16.0% reasoning gain and 4.05x inference speedup over InternVL3
- **Key features**: Visual Resolution Router (ViR) reduces tokens by 50% while maintaining performance; GUI interaction, embodied agency, 3D vision perception, industrial image analysis
- **Significance**: Narrows gap with GPT-5 in multimodal tasks; open-sourced training code
- **Source**: [Blog](https://internvl.github.io/blog/2025-08-26-InternVL-3.5/) | [arXiv](https://arxiv.org/abs/2508.18265)

#### Tarsier2 (January 2025) — BEST FOR VIDEO DESCRIPTION
- **Architecture**: 7B parameters (ByteDance)
- **Video capabilities**: Outperforms GPT-4o (+2.8% F1 on DREAM-1K) and Gemini 1.5 Pro (+5.8% F1) in detailed video description; +8.6% advantage over GPT-4o in human evaluations
- **Training**: 40M video-text pairs, fine-grained temporal alignment, DPO optimization
- **SOTA on**: 15 public benchmarks (video QA, grounding, hallucination tests, embodied QA)
- **Source**: [arXiv](https://arxiv.org/abs/2501.07888) | [GitHub](https://github.com/bytedance/tarsier)

#### LLaVA-OneVision-1.5 (2025)
- **Performance**: 8B variant outperforms Qwen2.5-VL-7B on 18/27 benchmarks; 4B surpasses Qwen2.5-VL-3B on all 27 benchmarks
- **Significance**: Fully open training framework; excellent for smaller model sizes
- **Source**: [arXiv](https://arxiv.org/html/2509.23661v3)

#### Qwen3-Omni (2025)
- **Capabilities**: Unified text, image, video, and audio understanding
- **Source**: [arXiv](https://arxiv.org/html/2509.17765v1)

### 2.2 VLM Recommendation for CCTV Analytics

| Task | Recommended Model | Rationale |
|---|---|---|
| Scene classification/understanding | Qwen3-VL-8B | Best spatial reasoning, object position/viewpoint detection |
| Detailed event narration | Tarsier2-7B | SOTA video description, fine temporal alignment |
| Batch video analysis | Qwen3-VL-32B or InternVL3.5 | Long-context, multi-hour processing |
| Edge/lightweight | Qwen3-VL-2B or LLaVA-OneVision-1.5-4B | Small footprint, competitive accuracy |
| Zero-shot activity recognition | Qwen3-VL + custom prompting | Spatial perception + temporal grounding |

### 2.3 Commercial Video Understanding APIs

#### Twelve Labs — Marengo 3.0 (December 2025)
- Tracks objects, movement, emotion, events through time
- 4-hour video support, 36 languages, 50% storage cost reduction
- Deep semantic search with natural language queries
- Available on Amazon Bedrock
- Marengo 2.7 deprecated mid-March 2026
- **Source**: [TwelveLabs](https://www.twelvelabs.io/)

#### Ambient Pulsar VLM (2026)
- Purpose-built reasoning VLM for physical security
- Trained on 1M+ hours of ethically sourced video
- Processes 500K+ hours daily; outperforms GPT-5 and Gemini 2.5 Pro in security contexts at 50x efficiency
- 150+ threat signatures; 95% false-alarm reduction
- **Source**: [Ambient.ai](https://www.ambient.ai/blog/introducing-ambient-pulsar-agentic-physical-security)

---

## 3. Automatic Camera Calibration (Zero-Config)

### 3.1 State-of-the-Art Approaches

#### GeoCalib (ECCV 2024) — RECOMMENDED
- **Approach**: Deep neural network that estimates vertical direction and camera intrinsics from a single image, combining learned features with geometric optimization
- **Key advantage**: More accurate than pure learning approaches; more robust than vanishing point methods; works in environments without visible straight lines
- **Output**: Camera intrinsics (focal length, principal point) + vertical direction
- **Source**: [GitHub](https://github.com/cvg/GeoCalib) | [arXiv](https://arxiv.org/abs/2409.06704)

#### DeepCalib
- Uses triplet attention mechanism for road direction vanishing point localization and camera pose estimation from a single image
- Benchmark dataset for monocular calibration from highway images
- **Source**: [GitHub](https://github.com/alexvbogdan/DeepCalib)

#### Deep-BrownConrady (January 2025)
- Predicts camera calibration AND distortion parameters from a single image
- Trained on mix of real and synthetic images
- Addresses Brown-Conrady distortion model parameters
- **Source**: [arXiv](https://arxiv.org/html/2501.14510v1)

#### Pedestrian-Based Calibration (Established Technique)
- **Method**: Estimate homography from pedestrians walking on ground plane
- **How it works**: When people walk along straight lines, head and foot positions constrain the camera geometry; bottom of bounding boxes establishes ground plane contact
- **Practical**: Requires only 4 correspondence points on ground plane; can be sourced from online maps (outdoor) or floor plans (indoor)
- **Research**: Multi-camera extrinsic calibration from pedestrian torsors; online calibration using ground plane induced homographies

### 3.2 Zero-Config Calibration Pipeline Recommendation

```
1. Initial: GeoCalib from first frame → intrinsics + vertical direction
2. Refine: Detect people walking → estimate ground plane homography
3. Continuous: Track height distribution → refine focal length estimate
4. Validate: Cross-check with vanishing point detection (when lines visible)
```

### 3.3 Key Resources
- [Awesome Deep Camera Calibration Survey](https://github.com/KangLiao929/Awesome-Deep-Camera-Calibration) — comprehensive paper list
- [Deep Learning for Camera Calibration Survey](https://arxiv.org/html/2303.10559v2) — 2023 survey, regularly updated

---

## 4. Open CCTV Datasets for Testing

### 4.1 Comprehensive Surveillance Datasets

| Dataset | Type | Scale | Annotations | URL |
|---|---|---|---|---|
| **VIRAT** | Outdoor surveillance | Multiple sites, USA | Activities, events | [viratdata.org](https://viratdata.org/) |
| **UCF-Crime** | Anomaly detection | 1,900 videos, 13 crime classes | Temporal anomaly labels | [UCF Crime](https://www.crcv.ucf.edu/projects/real-world/) |
| **ShanghaiTech Campus** | Anomaly detection | 13 scenes, 130 abnormal events, 270K+ frames | Pixel-level anomaly labels | [ShanghaiTech](https://svip-lab.github.io/dataset/campus_dataset.html) |
| **CUHK Avenue** | Anomaly detection | Single avenue scene | Anomaly frame labels | Standard benchmark |
| **UCSD Pedestrian** | Anomaly detection | 2 scenes (Ped1, Ped2) | Anomaly frame labels | Standard benchmark |
| **MOT17/MOT20** | Multi-object tracking | Dense pedestrian scenes | Bounding boxes, IDs | [motchallenge.net](https://motchallenge.net/) |
| **DanceTrack** | Tracking (uniform appearance) | Group dancing | Track IDs | [dancetrack.github.io](https://dancetrack.github.io/) |
| **CRxK (2025)** | Crime re-enactment | 13 categories (assault, intoxication, etc.) | Multi-camera annotations | [Nature](https://www.nature.com/articles/s41598-025-15058-w) |
| **WatchoutPed (2025)** | Vulnerable pedestrian anticipation | CCTV footage | Pedestrian vulnerability labels | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0950705125003995) |
| **CQAD (2025)** | Image quality assessment | 120 ref images, indoor/outdoor, day/night | Quality scores | [JMIS](https://www.jmis.org/archive/view_article?pid=jmis-12-3-81) |

### 4.2 Specialized Datasets

| Dataset | Focus | Notes |
|---|---|---|
| **UCF-Crime-DVS (2025)** | Event-based anomaly detection | Dynamic vision sensors, high temporal resolution |
| **UCVL Benchmark** | VLM evaluation on crime | 16,990 LLM-generated QA pairs from UCF-Crime |
| **SDNormal (2025)** | Scene-dependent anomalies | 31 scenes, 7 anomaly types, synthetic |
| **SportsMOT** | Multi-sport tracking | Diverse motion patterns |
| **EPFL Multi-Camera Pedestrian** | Multi-camera tracking | Calibrated multi-view pedestrian data |
| **Objects365** | General detection pretraining | 365 categories, 2M images |

### 4.3 Dataset Gaps for Zero-Config Platform
Missing datasets that would need to be created or sourced:
- **Multi-environment single-system**: Same analytics across parking lot + warehouse + hospital
- **Fisheye CCTV**: Very few labeled fisheye surveillance datasets
- **Thermal CCTV with person annotations**: Limited availability
- **Long-duration continuous**: Most datasets are clips, not 24-hour continuous feeds
- **Ground-truth zone definitions**: No standard dataset with pre-defined zones and flow patterns

---

## 5. Edge Deployment & Model Optimization

### 5.1 Hardware Platforms (2026)

#### NVIDIA Jetson T4000 (Q2 2026) — NEXT GENERATION
- **Performance**: 1,200 FP4 TFLOPS; 4x performance of previous gen
- **Memory**: 64 GB
- **Power**: 70W configurable envelope
- **Architecture**: Blackwell GPU, 1,536 CUDA cores, 64 Tensor cores
- **Software**: JetPack 7.1, TensorRT Edge-LLM SDK for VLMs on edge
- **Price**: $1,999 at 1K volume
- **Source**: [NVIDIA Blog](https://developer.nvidia.com/blog/accelerate-ai-inference-for-edge-and-robotics-with-nvidia-jetson-t4000-and-nvidia-jetpack-7-1)

#### NVIDIA Jetson Thor
- **Performance**: 2,070 FP4 TFLOPS; 128 GB memory; 7.5x AI perf of AGX Orin
- **Power**: 40-130W
- **Target**: High-end robotics and edge AI

#### NVIDIA Jetson AGX Orin (Current Generation)
- **Performance**: Up to 275 TOPS (INT8)
- **Capabilities**: 22x 1080P streams simultaneously (NRU-220S)
- **Ecosystem**: AI NVR reference designs, DeepStream SDK, PeopleNet 2.6
- **Source**: [NVIDIA Jetson](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)

### 5.2 Software Optimization Stack

#### NVIDIA Model Optimizer (formerly TensorRT Model Optimizer)
- Unified library: quantization, pruning, distillation, speculative decoding
- Supports: FP32, FP16, INT8, FP8, NVFP4, INT4
- Integration: TensorRT-LLM, TensorRT, vLLM, SGLang
- **Source**: [GitHub](https://github.com/NVIDIA/Model-Optimizer)

#### Quantization Techniques (2025-2026)
| Technique | Bit Width | Use Case | Accuracy Impact |
|---|---|---|---|
| **FP16** | 16-bit | Standard deployment | Negligible |
| **INT8** | 8-bit | Edge deployment | <1% AP drop |
| **FP8** | 8-bit float | Latest GPUs | Minimal |
| **INT4 (AWQ)** | 4-bit | Memory-constrained | 1-3% AP drop |
| **NVFP4** | 4-bit float | NVIDIA-specific | Optimized for Blackwell |

#### Key Frameworks
- **ONNX Runtime**: Cross-hardware inference, EP framework for hardware acceleration
- **TensorRT**: NVIDIA-optimized inference, dynamic batching
- **TensorRT Edge-LLM**: Open-source C++ SDK for LLMs/VLMs on Jetson
- **vLLM**: High-throughput LLM serving with PagedAttention

### 5.3 NVIDIA DeepStream Pipeline for CCTV
- **Architecture**: VST (camera discovery, ingestion, storage) + DeepStream (real-time perception)
- **Detection**: PeopleNet v2.6 (person, face, bag detection)
- **Tracking**: NvDCF with ReID model for long-term association
- **Analytics**: NvDsAnalytics plugin for entry/exit counting, ROI-based analytics
- **Output**: Kafka streaming for downstream processing
- **Source**: [NVIDIA DeepStream Docs](https://docs.nvidia.com/metropolis/deepstream/dev-guide/)

### 5.4 Deployment Recommendation for Batch Processing
For a batch-processing system (not real-time edge):
1. **Detection**: YOLO26-M or RF-DETR exported to ONNX/TensorRT
2. **Tracking**: BoT-SORT-ReID in batch mode
3. **VLM analysis**: Qwen3-VL-8B via vLLM with FP8 quantization
4. **Infrastructure**: GPU server (A100/H100) for batch; optional Jetson Orin for on-premise
5. **Pipeline**: FFmpeg decode → detection → tracking → zone analytics → VLM scene summary

---

## 6. Zero-Configuration & Self-Adaptive Systems

### 6.1 Existing Approaches

#### Avigilon Self-Learning Video Analytics
- Works out-of-the-box without manual calibration
- Point-and-shoot system; learns scene over time
- Adapts to changing conditions; prioritizes events based on user feedback
- **Weakness**: Proprietary, expensive, limited to Avigilon ecosystem

#### AXIS Object Analytics
- Pre-installed on Axis cameras
- Zero-configuration object classification (person, vehicle)
- Edge-computed analytics
- **Source**: [Axis](https://www.axis.com/products/axis-object-analytics)

#### SharpAI DeepCamera (Open Source)
- Auto-detects GPU and converts models to fastest native format
- AI-driven environment config: detects GPU, installs framework, converts models, verifies setup
- Pluggable AI skills architecture
- VLM support: Qwen, DeepSeek, SmolVLM, LLaVA
- **Source**: [GitHub](https://github.com/SharpAI/DeepCamera)

### 6.2 AutoML for Video Analytics
- Research on jointly configuring service and network parameters using Bayesian online learning
- Optimizes analytics accuracy subject to frame rate constraints
- Dynamically adapts to available compute and network bandwidth
- **Reference**: [AutoML for Video Analytics (INFOCOM)](https://jaayala.github.io/papers/21_infocom_2.pdf)

### 6.3 Zero-Config Architecture Recommendations

```
Zero-Config Pipeline:
1. Camera connects → auto-detect resolution, FPS, FOV
2. GeoCalib → auto-calibrate from first frames
3. Run detection for 5 min → auto-determine:
   - Scene type (indoor/outdoor/parking/retail/warehouse)
   - Lighting conditions (day/night/mixed)
   - Camera mount (overhead/wall/pole)
   - Typical occupancy level
4. VLM scene description → classify environment
5. Auto-select optimal:
   - Detection model variant (Nano/Small/Medium)
   - Tracking parameters (association threshold, track lifetime)
   - Zone suggestions based on detected walkways/entrances
   - Alert thresholds based on normal activity patterns
6. Continuous adaptation:
   - Monitor detection confidence → adjust thresholds
   - Track scene changes (lighting, occupancy patterns)
   - Re-calibrate periodically using pedestrian observations
```

### 6.4 Self-Supervised Scene Understanding
- Train on normal behavior patterns → detect deviations
- Temporal proxy tasks: predict inter-frame intervals to learn motion continuity
- Multi-head self-attention for capturing context across entire sequences
- Achieves 38 FPS inference on benchmark datasets
- **Key approach**: Unsupervised learning where model trains only on "normal" data

---

## 7. Privacy-Preserving Analytics

### 7.1 EU AI Act Impact on CCTV (2025-2026)

#### Key Regulatory Points
- **Banned**: Mass real-time facial recognition in public spaces (with narrow exceptions: searching for victims of serious crimes, preventing terrorist threats — under strict judicial oversight)
- **High-risk classification**: Non-biometric AI video analytics classified as high-risk systems; require extensive testing before market placement
- **Transparency rules**: Come into effect August 2026
- **Practical impact**: Any CCTV analytics product sold in EU must comply with high-risk AI system requirements

#### Compliance Strategy
1. **No biometric identification by default** — use pose estimation, silhouettes, or anonymized representations
2. **On-device processing** — minimize data transmission of raw video
3. **Data minimization** — extract analytics, discard raw frames
4. **Audit trail** — log all processing decisions
5. **Human oversight** — automated alerts require human review

### 7.2 Privacy-Preserving Technologies

| Technique | Maturity | Application |
|---|---|---|
| **Pose estimation (RTMPose)** | Production-ready | Replace face/body appearance with skeleton |
| **Real-time video anonymization** | Production-ready | Blur faces/bodies at edge or post-processing |
| **Differential privacy** | Mature | Add noise to aggregate analytics outputs |
| **Federated learning** | Research/early production | Train models across cameras without centralizing data |
| **Homomorphic encryption** | Research | Process encrypted video (impractical for real-time) |
| **On-device processing** | Production-ready | All inference on local hardware |

### 7.3 Federated Learning for CCTV
- **Architecture**: Each camera/edge device trains locally; shares only model parameters with aggregator
- **Benefits**: No raw video leaves the device; models adapt to local scene characteristics
- **Research**: LSTM models trained across multiple CCTV cameras using FL to predict future object occurrences
- **Challenges**: Communication overhead, non-IID data across cameras, model convergence
- **Source**: [Federated Learning for Surveillance Survey](https://www.mdpi.com/2079-9292/14/17/3500)

### 7.4 Practical Privacy Architecture
```
Privacy-by-Design Pipeline:
1. Video ingested locally (never leaves device/server)
2. Detection → bounding boxes only (no face embeddings stored)
3. Tracking → anonymous track IDs (no ReID features persisted)
4. Pose estimation → skeleton data only
5. Analytics output: counts, heatmaps, dwell times, zone transitions
6. VLM analysis on anonymized frames (faces blurred)
7. Raw video deleted after processing (configurable retention)
8. Only aggregate analytics stored/transmitted
```

---

## 8. Competitive Landscape

### 8.1 Market Overview
- **Global video surveillance market**: $56.11B (2025) → $88.06B by 2031 (7.8% CAGR)
- **AI video analytics market**: $5.04B (2025) → $17.20B by 2030 (23.35% CAGR)
- **Cloud VMS**: Growing at ~16% annually, fastest segment
- **AI-driven systems**: ~33% of new deployments in 2025

### 8.2 Key Competitors Deep Dive

#### Tier 1: Enterprise Leaders

| Company | Strengths | Weaknesses | Pricing |
|---|---|---|---|
| **Verkada** | Cloud-native simplicity; all-inclusive licensing; tight HW-SW integration | Proprietary cameras required; privacy concerns (2021 breach); expensive | $$$$ |
| **Avigilon (Motorola)** | Self-learning analytics; flexible HW support; government/enterprise focus | Complex deployment; expensive; on-premise heavy | $$$$ |
| **Genetec** | #1 VMS market share; unified security platform; natural language search | Analytics is add-on, not core; complex licensing | $$$ |
| **Milestone Systems (Canon)** | Largest open-platform VMS; BriefCam integration | BriefCam license separate; complex architecture | $$$ |

#### Tier 2: AI-First Players

| Company | Strengths | Weaknesses |
|---|---|---|
| **Ambient.ai** | Pulsar VLM (outperforms GPT-5 for security); agentic AI; 150+ threat signatures; 95% false alarm reduction | Enterprise-only; expensive; closed ecosystem |
| **BriefCam** | Video Synopsis (condenses hours to minutes); forensic search; cross-camera tracking | High cost; high compute requirements; limited video format support; now part of Milestone |
| **Coram AI** | Works with any IP camera; natural language alerts; weapon/fall detection; free tier | Newer company; limited enterprise track record |
| **Eagle Eye Networks** | Cloud-native; automations engine; global reach | Analytics less sophisticated than specialists |
| **Spot AI** | Fastest-growing AI video startup; natural language search | Younger product; less proven at scale |

#### Tier 3: Open Source / Emerging

| Project | Approach | Status |
|---|---|---|
| **DeepCamera (SharpAI)** | Open-source AI NVR; VLM-powered; agentic alerts via Telegram/Discord | Active development; community-driven |
| **Frigate NVR** | Open-source NVR with detection | Popular in home automation; limited analytics |
| **Viseron** | Open-source video analytics | Early stage |

### 8.3 Competitive Gap Analysis

**Where existing products fall short (opportunity for disruption):**

1. **Zero-configuration**: No product truly works out-of-the-box. Even "self-learning" systems like Avigilon require camera-by-camera setup, zone definition, and rule configuration.

2. **People-centric analytics beyond counting**: Most products count people and detect intrusions. Few provide heatmaps, dwell time analysis, flow patterns, queue detection, and behavioral insights automatically.

3. **Batch processing / forensic analytics**: Market is focused on real-time. Batch analysis of historical footage is underserved — BriefCam's video synopsis is closest but expensive and limited.

4. **Universal camera support with intelligence**: Coram AI supports any IP camera but analytics are basic. Verkada has great analytics but requires their cameras.

5. **Privacy-by-design**: Most products treat privacy as an afterthought. EU AI Act compliance is a differentiator.

6. **Open/affordable**: Enterprise products are $$$. DeepCamera is open but raw. There's a gap for a polished, affordable, AI-first product.

7. **VLM-powered scene understanding**: Only Ambient.ai has a purpose-built VLM (Pulsar). Everyone else uses traditional CV pipelines. Using open-source VLMs (Qwen3-VL) is a massive cost advantage.

---

## 9. Emerging Paradigms

### 9.1 Foundation Models for Video Understanding

#### InternVideo2 / InternVideo-Next (2025)
- **Architecture**: Progressive training — masked video modeling + crossmodal contrastive learning + next token prediction
- **Scale**: Video encoder up to 6B parameters
- **InternVideo-Next**: Encoder-Predictor-Decoder with predictor as latent world model; two-stage pretraining for semantically consistent yet detail-preserving latent space
- **Relevance to CCTV**: Pre-trained video understanding backbone that can be fine-tuned for surveillance tasks
- **Source**: [GitHub](https://github.com/OpenGVLab/InternVideo) | [arXiv](https://arxiv.org/abs/2403.15377)

#### VideoMAE
- Self-supervised video pre-training with extremely high masking ratio (90-95%)
- Tube masking strategy: mask random spatiotemporal tubes
- Vanilla ViT backbone
- **Relevance**: Pre-train on unlabeled CCTV footage, then fine-tune for specific tasks

### 9.2 World Models for Physical Scene Understanding
- InternVideo-Next's predictor acts as a latent world model
- Can predict future scene states from current observations
- **Relevance to CCTV**: Predict where people will go; detect anomalies when predictions fail; understand physical scene layout

### 9.3 3D Scene Reconstruction from Monocular CCTV

#### 3D Gaussian Splatting (3DGS) Advances
- **HI-SLAM2**: Geometry-aware Gaussian SLAM for fast monocular reconstruction (TRO 2025)
- **DepthSplat**: Integrates monocular depth estimation with Gaussian splatting
- **MAGiC-SLAM (CVPR 2025)**: Multi-agent globally consistent SLAM
- **BARD-GS (CVPR 2025)**: Blur-aware reconstruction of dynamic scenes
- **Forensic applications**: Indoor crime scene investigation using 3DGS

#### NeRF Integration
- **ExpanDyNeRF**: Monocular NeRF with Gaussian splatting priors for large-angle synthesis
- **Practical for CCTV**: Build 3D model of monitored space from camera feeds; enable virtual viewpoint synthesis; improve occlusion reasoning

### 9.4 Agentic AI for Autonomous Monitoring

#### Market Context
- **Market size**: $4.10B (2025) → $5.67B (2026) in law enforcement/surveillance; 38.4% CAGR to 2035
- **2026 is "the year of agentic AI"** for physical security

#### Key Capabilities
- **Autonomous situational analysis**: AI agents analyze complex scenes without human intervention
- **Automated initial response**: Execute response protocols (lock doors, alert security, activate lighting)
- **Natural language rules**: Security teams define monitoring rules in plain English
- **Semantic search**: Search video archives with conversational queries
- **Adaptive video walls**: Dynamic prioritization of streams showing most interesting activity

#### Examples
- **Ambient.ai Pulsar**: Agentic video walls, activity notifications, semantic search
- **Cloudastructure (Feb 2026)**: Solar-powered agentic AI surveillance for critical infrastructure
- **Twelve Labs**: "Video intelligence is going agentic"

#### Architecture for Agentic CCTV
```
Agentic CCTV Pipeline:
1. Perception Layer: YOLO26 detection + tracking (continuous)
2. Understanding Layer: Qwen3-VL scene analysis (periodic/triggered)
3. Memory Layer: Historical patterns, learned normalcy per scene
4. Reasoning Layer: LLM agent evaluates situation against rules + context
5. Action Layer: Generate alerts, trigger automations, update dashboard
6. Feedback Loop: User responses refine agent behavior
```

---

## 10. Action Recognition & Behavior Analysis

### 10.1 Anomaly Detection Approaches

#### Self-Supervised / Unsupervised (Recommended for Zero-Config)
- **Approach**: Train only on "normal" data; any deviation is anomalous
- **Methods**:
  - Temporal proxy tasks: predict inter-frame intervals → learn motion continuity
  - Multi-head self-attention for context across input sequence
  - Autoencoder reconstruction error → high error = anomaly
  - Optical flow reconstruction + erased frame prediction
- **Performance**: AUROC 97.7% (UCSD Ped2), 89.7% (Avenue), 75.8% (ShanghaiTech)
- **Speed**: 36-38 FPS on benchmarks
- **Source**: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0031320325008593)

#### Weakly Supervised
- **PASS-CCTV**: Proactive anomaly surveillance for adverse conditions
- **Self-Paced Multiple Instance Learning**: Handles noisy weak labels
- **VLM-based**: Compact VLMs for clip-level surveillance anomaly detection under weak supervision

#### Multi-Camera Spatiotemporal (2025)
- **MS-GAT**: Multi-Scale Graph Attention Networks for interaction-aware anomaly detection
- **Result**: Up to 30% reduction in false positives
- **Source**: [Nature Scientific Reports](https://www.nature.com/articles/s41598-025-12388-7)

### 10.2 Specific Activity Detection

| Activity | Detection Approach | Maturity |
|---|---|---|
| **Loitering** | Dwell time threshold per zone | Production-ready |
| **Fighting/assault** | Pose estimation + sudden motion patterns | Research/early production |
| **Falling** | Pose estimation (vertical-to-horizontal transition) | Production-ready |
| **Queuing** | Line detection + wait time estimation | Production-ready |
| **Crowd formation** | Density estimation + clustering | Production-ready |
| **Running** | Velocity threshold + pose | Production-ready |
| **Abandoned objects** | Static object detection over time | Production-ready |
| **Wrong direction** | Flow analysis vs. expected patterns | Production-ready |
| **Intrusion** | Zone violation detection | Production-ready |
| **Tailgating** | Multiple persons in single-person zone | Emerging |

### 10.3 VLM-Based Zero-Shot Activity Recognition
- Use Qwen3-VL to describe what's happening in video clips
- No training required — define activities in natural language prompts
- Example prompt: "Analyze this CCTV clip. Is anyone: fighting, falling, running, loitering (standing still for >30s), or leaving an unattended bag?"
- **Advantage**: Instantly supports new activity types by updating prompts
- **Disadvantage**: Higher latency; may miss subtle activities; requires GPU

### 10.4 Behavior Analysis Recommendation
```
Two-Tier Architecture:
Tier 1 (Real-time/Batch, Always On):
  - Detection + Tracking → dwell time, zone transitions, counts
  - Pose estimation → fall detection, basic activity classification
  - Density estimation → crowd analytics

Tier 2 (VLM-Powered, Periodic/Triggered):
  - Scene description → "What's happening?"
  - Anomaly investigation → "Is this behavior normal?"
  - Activity classification → zero-shot from natural language
  - Triggered when Tier 1 detects anomaly or on schedule
```

---

## 11. Strategic Recommendations

### 11.1 Technology Stack for a Disruptive Zero-Config CCTV Analytics Platform

#### Core Detection & Tracking
- **Primary detector**: YOLO26-M (ONNX/TensorRT) — NMS-free, small-target aware, quantization-friendly
- **Accuracy detector**: RF-DETR (Apache 2.0) — for batch processing where speed is less critical
- **Tracker**: BoT-SORT-ReID — proven, well-documented, strong re-identification
- **Pose**: RTMPose-m via rtmlib — no heavy dependencies, excellent speed-accuracy

#### Scene Understanding (VLM)
- **Primary**: Qwen3-VL-8B (Apache 2.0) — best spatial reasoning, hour-long video support, 2B variant for edge
- **Video description**: Tarsier2-7B — when detailed event narration is needed
- **Serving**: vLLM with FP8 quantization

#### Auto-Calibration
- **Initial**: GeoCalib (single-frame intrinsics + vertical)
- **Refinement**: Pedestrian-based ground plane homography
- **Continuous**: Height distribution tracking for focal length validation

#### Privacy
- Default anonymized pipeline: pose skeletons + blurred faces
- On-device processing wherever possible
- EU AI Act high-risk system compliance from day one

### 11.2 Key Differentiators vs. Competition

1. **True zero-config**: Camera connects → analytics flow. No zone drawing, no rule setting, no calibration.
2. **VLM-first architecture**: Use Qwen3-VL for scene understanding instead of hand-coded rules — instantly adaptable to any environment.
3. **Privacy-by-design**: Only analytics leave the processing node. EU AI Act compliant.
4. **Open-source core**: Build on Apache 2.0 models (RF-DETR, Qwen3-VL, D-FINE). No Ultralytics AGPL dependency for commercial use.
5. **Batch-processing focus**: Underserved market. Process historical footage for insights, not just real-time alerts.
6. **Agentic architecture**: LLM agent that reasons about scenes, adapts rules, and communicates findings in natural language.

### 11.3 Licensing Considerations

| Component | License | Commercial Use |
|---|---|---|
| YOLO26 | AGPL-3.0 (Ultralytics) | Requires Ultralytics commercial license |
| RF-DETR | Apache 2.0 | Free for commercial use |
| D-FINE | Apache 2.0 | Free for commercial use |
| Qwen3-VL | Apache 2.0 | Free for commercial use |
| InternVL3.5 | MIT | Free for commercial use |
| Tarsier2 | Apache 2.0 | Free for commercial use |
| BoT-SORT | Unknown/research | Check license before commercial use |
| RTMPose / rtmlib | Apache 2.0 | Free for commercial use |
| GeoCalib | Research | Check license for commercial use |

### 11.4 Risk Factors
1. **VLM latency**: Even 8B models require significant GPU for batch processing of video
2. **YOLO licensing**: AGPL requires commercial license; RF-DETR or D-FINE as Apache alternatives
3. **EU AI Act compliance**: High-risk classification means significant documentation and testing burden
4. **Privacy regulations evolving**: Different jurisdictions, different rules
5. **Accuracy in edge cases**: Night, fog, extreme fisheye still challenging
6. **Competition from Ambient.ai**: They have purpose-built VLM + first-mover advantage in agentic security

### 11.5 Research Papers to Track

| Paper | Venue | Relevance |
|---|---|---|
| YOLO26 | arXiv 2509.25164 | Latest detection architecture |
| RF-DETR | ICLR 2026 | Best real-time transformer detector |
| D-FINE | ICLR 2025 Spotlight | Fine-grained detection |
| Qwen3-VL Technical Report | arXiv 2511.21631 | Primary VLM |
| InternVL3.5 | arXiv 2508.18265 | Alternative VLM |
| Tarsier2 | arXiv 2501.07888 | Video description SOTA |
| GeoCalib | ECCV 2024 | Auto-calibration |
| Deep Camera Calibration Survey | arXiv 2303.10559 | Calibration overview |
| CAMELTrack | arXiv 2505.01257 | Latest MOT |
| Video Anomaly Detection Survey | Sensors 2023 | Anomaly detection overview |
| InternVideo-Next | arXiv 2512.01342 | Video foundation model |

---

## Sources

### Detection Models
- [Ultralytics YOLO26 Docs](https://docs.ultralytics.com/models/yolo26/)
- [YOLO26 arXiv Paper](https://arxiv.org/abs/2509.25164)
- [YOLO26 Roboflow Guide](https://blog.roboflow.com/yolo26/)
- [YOLOv12 OpenReview](https://openreview.net/forum?id=gCvByDI4FN)
- [YOLOv12 Ultralytics Docs](https://docs.ultralytics.com/models/yolo12/)
- [RF-DETR GitHub (Roboflow)](https://github.com/roboflow/rf-detr)
- [RF-DETR arXiv](https://arxiv.org/abs/2511.09554)
- [RF-DETR Roboflow Blog](https://blog.roboflow.com/rf-detr/)
- [D-FINE GitHub](https://github.com/Peterande/D-FINE)
- [D-FINE arXiv](https://arxiv.org/html/2410.13842v1)
- [Best Object Detection Models 2025 (Roboflow)](https://blog.roboflow.com/best-object-detection-models/)

### Tracking
- [MOTChallenge](https://motchallenge.net/)
- [DanceTrack](https://dancetrack.github.io/)
- [BoT-SORT arXiv](https://arxiv.org/abs/2206.14651)
- [CAMELTrack arXiv](https://arxiv.org/html/2505.01257)
- [RAMA (Nature Scientific Reports)](https://www.nature.com/articles/s41598-025-07276-z)
- [MOT Review (Springer)](https://link.springer.com/article/10.1007/s10462-025-11212-y)

### Vision-Language Models
- [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
- [Qwen3-VL arXiv](https://arxiv.org/abs/2511.21631)
- [Qwen3-VL Blog](https://qwen.ai/blog?id=99f0335c4ad9ff6153e517418d48535ab6d8afef)
- [InternVL3.5 Blog](https://internvl.github.io/blog/2025-08-26-InternVL-3.5/)
- [InternVL3.5 arXiv](https://arxiv.org/abs/2508.18265)
- [InternVL GitHub](https://github.com/OpenGVLab/InternVL)
- [Tarsier2 arXiv](https://arxiv.org/abs/2501.07888)
- [Tarsier2 GitHub](https://github.com/bytedance/tarsier)
- [LLaVA-OneVision-1.5 arXiv](https://arxiv.org/html/2509.23661v3)
- [Best Open-Source VLMs 2026 (Labellerr)](https://www.labellerr.com/blog/top-open-source-vision-language-models/)
- [Top VLMs 2026 (DataCamp)](https://www.datacamp.com/blog/top-vision-language-models)

### Camera Calibration
- [GeoCalib GitHub](https://github.com/cvg/GeoCalib)
- [GeoCalib arXiv](https://arxiv.org/abs/2409.06704)
- [DeepCalib GitHub](https://github.com/alexvbogdan/DeepCalib)
- [Deep-BrownConrady arXiv](https://arxiv.org/html/2501.14510v1)
- [Awesome Deep Camera Calibration](https://github.com/KangLiao929/Awesome-Deep-Camera-Calibration)
- [Camera Calibration Survey](https://arxiv.org/html/2303.10559v2)
- [Homography from Pedestrians (Galliot)](https://galliot.us/blog/camera-calibration-using-homography-estimation/)

### Datasets
- [VIRAT Video Data](https://viratdata.org/)
- [UCF-Crime Dataset](https://www.crcv.ucf.edu/projects/real-world/)
- [ShanghaiTech Campus](https://svip-lab.github.io/dataset/campus_dataset.html)
- [CRxK Dataset (Nature)](https://www.nature.com/articles/s41598-025-15058-w)
- [WatchoutPed (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S0950705125003995)
- [CQAD Dataset](https://www.jmis.org/archive/view_article?pid=jmis-12-3-81)
- [UCF-Crime-DVS arXiv](https://arxiv.org/abs/2503.12905)
- [EPFL Multi-Camera Pedestrian](https://www.epfl.ch/labs/cvlab/data/data-pom-index-php/)

### Edge Deployment
- [NVIDIA Jetson T4000 Blog](https://developer.nvidia.com/blog/accelerate-ai-inference-for-edge-and-robotics-with-nvidia-jetson-t4000-and-nvidia-jetpack-7-1)
- [NVIDIA Jetson Thor](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/)
- [NVIDIA Jetson Orin](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)
- [NVIDIA Model Optimizer GitHub](https://github.com/NVIDIA/Model-Optimizer)
- [NVIDIA DeepStream Docs](https://docs.nvidia.com/metropolis/deepstream/dev-guide/)
- [NVIDIA AI NVR](https://docs.nvidia.com/moj/setup/ai-nvr.html)
- [TinyML Resources](https://github.com/umitkacar/awesome-tinyml)

### Privacy & Regulation
- [EU AI Act (Dallmeier)](https://www.dallmeier.com/about-us/dallmeier-blog/video-security-technology-and-biometric-facial-recognition-under-new-eu-ai-act-ai-regulation)
- [2026 Guide to AI CCTV](https://www.clevelandsecuritycameras.com/post/the-2026-guide-to-ai-cctv-how-smart-analytics-new-privacy-laws-change-everything)
- [EU AI Act Official](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
- [Federated Learning for Surveillance](https://www.mdpi.com/2079-9292/14/17/3500)
- [Privacy-Preserving Video Analytics (SecureRedact)](https://www.secureredact.ai/articles/protect-sensitive-footage-ai-video-analytics)
- [Irisity Anonymization & GDPR](https://irisity.com/blog/anonymization-gdpr/)

### Competitive Landscape
- [Ambient.ai Pulsar Announcement](https://www.ambient.ai/blog/introducing-ambient-pulsar-agentic-physical-security)
- [Ambient.ai Platform](https://www.ambient.ai/)
- [BriefCam](https://www.briefcam.com/)
- [BriefCam 2025 R1](https://www.milestonesys.com/resources/content/articles/briefcam-2025-r1-smarter-video-analytics-stronger-performance/)
- [Coram AI](https://www.coram.ai/)
- [Genetec Market Position](https://www.genetec.com/press-center/press-releases/2025/08/genetec-continues-to-dominate-video-surveillance-software-market-according-to-latest-analyst-reports)
- [Eagle Eye Networks](https://www.een.com/)
- [DeepCamera (SharpAI)](https://github.com/SharpAI/DeepCamera)
- [Avigilon vs Verkada 2026](https://www.avigilon.com/avigilon-vs-verkada)
- [11 Best AI Video Analytics Companies 2026](https://memories.ai/blogs/11_Best_AI_Video_Analytics_Companies_in_2026)

### Emerging Paradigms
- [InternVideo GitHub](https://github.com/OpenGVLab/InternVideo)
- [InternVideo2 arXiv](https://arxiv.org/abs/2403.15377)
- [InternVideo-Next arXiv](https://www.arxiv.org/pdf/2512.01342)
- [Twelve Labs](https://www.twelvelabs.io/)
- [Twelve Labs Marengo 3.0](https://www.hpcwire.com/aiwire/2025/12/01/twelvelabs-launches-marengo-3-0-video-understanding-model-on-twelvelabs-and-amazon-bedrock/)
- [Agentic AI in Surveillance Market](https://www.precedenceresearch.com/agentic-ai-in-law-enforcement-and-surveillance-market)
- [Video Intelligence Going Agentic](https://www.twelvelabs.io/blog/video-intelligence-is-going-agentic)
- [3D Gaussian Splatting Papers](https://mrnerf.github.io/awesome-3D-gaussian-splatting/)
- [BARD-GS (CVPR 2025)](https://openaccess.thecvf.com/content/CVPR2025/papers/Lu_BARD-GS_Blur-Aware_Reconstruction_of_Dynamic_Scenes_via_Gaussian_Splatting_CVPR_2025_paper.pdf)

### Action Recognition & Anomaly Detection
- [Multi-Camera Anomaly Detection (Nature)](https://www.nature.com/articles/s41598-025-12388-7)
- [Self-Supervised Anomaly Detection (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0031320325008593)
- [Video Anomaly Detection Survey (Sensors)](https://www.mdpi.com/1424-8220/23/11/5024)
- [Video Anomaly Detection 10-Year Survey](https://arxiv.org/html/2405.19387v1)
- [Anomaly Detection Survey (Springer)](https://link.springer.com/article/10.1007/s10462-024-11092-8)
- [VLM Anomaly Detection Benchmark](https://pmc.ncbi.nlm.nih.gov/articles/PMC12653427/)

### Pose Estimation
- [RTMPose Paper](https://arxiv.org/html/2303.07399v2)
- [RTMW Whole-Body](https://arxiv.org/html/2407.08634v1)
- [rtmlib GitHub](https://github.com/Tau-J/rtmlib)
- [MMPose](https://mmpose.com/)
- [Pose Estimation 2026 Guide (Datature)](https://datature.io/blog/what-is-pose-estimation-keypoint-detection-explained-2026)
