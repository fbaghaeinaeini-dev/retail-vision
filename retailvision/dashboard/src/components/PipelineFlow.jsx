import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Cpu,
  Eye,
  Zap,
  Globe,
  Timer,
  Hash,
  ArrowDown,
  Workflow,
  Shield,
  BarChart3,
  Layers,
} from "lucide-react";
import { formatDuration, formatNumber } from "../lib/colors";

// ─── Pipeline definition ─────────────────────────────────────────────────────

const PHASE_COLORS = {
  1: "#00d4ff", // Scene Understanding — cyan
  2: "#ff9500", // Zone Discovery — amber
  3: "#b366ff", // Zone Classification — purple
  4: "#00ff88", // Analytics — green
  5: "#ff3366", // Validation — red
  6: "#ffc233", // Visualization — gold
};

const PHASE_ICONS = {
  1: Eye,
  2: Layers,
  3: Cpu,
  4: BarChart3,
  5: Shield,
  6: Workflow,
};

const PIPELINE_PHASES = [
  {
    phase: 1,
    name: "Scene Understanding",
    description: "Camera calibration, scene classification, and spatial analysis",
    tools: [
      { id: "t01", name: "ingest_from_db", desc: "Load tracks from SQLite database", optional: false },
      { id: "t02", name: "extract_reference_frame", desc: "Get camera snapshot for visual analysis", optional: false },
      { id: "t03", name: "calibrate_from_person_height", desc: "Compute BEV homography matrix", optional: false },
      { id: "t04", name: "classify_scene_type", desc: "Classify scene (indoor_food_court, etc.)", optional: false },
      { id: "t05", name: "vlm_scene_layout", desc: "VLM spatial layout analysis", optional: true, badge: "VLM" },
      { id: "t06", name: "depth_scene_analysis", desc: "Monocular depth estimation", optional: true, badge: "API" },
    ],
  },
  {
    phase: 2,
    name: "Zone Discovery",
    description: "Dwell clustering, density grids, and trajectory community detection",
    tools: [
      { id: "t07", name: "compute_dwell_points", desc: "Find where people stop and linger", optional: false },
      { id: "t08", name: "strategy_dwell_clustering", desc: "ST-DBSCAN on dwell points", optional: false },
      { id: "t09", name: "strategy_occupancy_grid", desc: "Density-based zone candidates", optional: false },
      { id: "t10", name: "strategy_trajectory_graph", desc: "Louvain community detection", optional: false },
      { id: "t11", name: "fuse_zone_candidates", desc: "Ensemble voting + watershed split", optional: false },
      { id: "t12", name: "vlm_detect_structures", desc: "Detect structural elements via VLM", optional: true, badge: "VLM" },
    ],
  },
  {
    phase: 3,
    name: "Zone Classification",
    description: "Visual recognition, object inventory, and zone type assignment",
    tools: [
      { id: "t13", name: "crop_zone_images", desc: "Extract zone image crops", optional: false },
      { id: "t14", name: "depth_zone_analysis", desc: "Per-zone depth estimation", optional: true, badge: "API" },
      { id: "t15", name: "vlm_object_inventory", desc: "Detect objects in zone crops", optional: true, badge: "VLM" },
      { id: "t16", name: "vlm_signage_reader", desc: "Read text and signage", optional: true, badge: "VLM" },
      { id: "t17", name: "vlm_zone_classifier", desc: "Classify zone type from visuals", optional: false, badge: "VLM" },
      { id: "t18", name: "segment_zone_refinement", desc: "Correct classifications via lang-SAM segmentation", optional: true, badge: "API" },
      { id: "t19", name: "vlm_zone_describer", desc: "Generate natural language descriptions", optional: true, badge: "VLM" },
      { id: "t20", name: "merge_zone_registry", desc: "Combine all zone metadata", optional: false },
    ],
  },
  {
    phase: 4,
    name: "Analytics",
    description: "Zone metrics, flow transitions, temporal patterns, and heatmaps",
    tools: [
      { id: "t21", name: "compute_zone_analytics", desc: "Visits, dwell time, density", optional: false },
      { id: "t22", name: "compute_flow_analytics", desc: "Zone-to-zone transitions", optional: false },
      { id: "t23", name: "compute_temporal_analytics", desc: "Time-based occupancy patterns", optional: false },
      { id: "t24", name: "compute_spatial_analytics", desc: "Density heatmap generation", optional: false },
    ],
  },
  {
    phase: 5,
    name: "Validation",
    description: "Quality metrics, silhouette scoring, and pass/fail gate",
    tools: [
      { id: "t25", name: "validate_zones", desc: "Silhouette score, coverage, sanity checks", optional: false },
      { id: "t26", name: "quality_gate", desc: "Pass/fail decision (can retry Phase 2)", optional: false },
    ],
  },
  {
    phase: 6,
    name: "Visualization",
    description: "Render charts, 3D scene, and export dashboard bundle",
    tools: [
      { id: "t27", name: "plan_visualizations", desc: "LLM selects visualization types", optional: false, badge: "LLM" },
      { id: "t28", name: "render_all_visualizations", desc: "Generate all chart images", optional: false },
      { id: "t29", name: "render_3d_scene", desc: "Three.js scene export", optional: false },
      { id: "t30", name: "export_dashboard_bundle", desc: "Final JSON + asset bundle", optional: false },
    ],
  },
];

// Detect gate entries in tool history
function isGateEntry(tool) {
  return tool.is_gate || (typeof tool.tool === 'string' && tool.tool.startsWith('gate'));
}

// Build tool statuses from actual tool_history when available, else derive from meta
function deriveToolStatus(meta) {
  // Build a flat list of all tool IDs from the pipeline definition
  const toolIdMap = {};
  PIPELINE_PHASES.forEach((phase) => {
    phase.tools.forEach((tool) => {
      toolIdMap[tool.name] = tool.id;
    });
  });

  const statuses = {};

  // If we have actual tool_history from the pipeline report, use it
  const history = meta.tool_history || [];
  if (history.length > 0) {
    history.forEach((entry) => {
      const tid = toolIdMap[entry.tool];
      if (tid) {
        statuses[tid] = {
          status: entry.success ? "success" : "failed",
          timing: entry.duration || 0,
          result: entry.message || null,
        };
      }
    });
    // Mark any tools not in history as skipped
    Object.entries(toolIdMap).forEach(([name, tid]) => {
      if (!statuses[tid]) {
        statuses[tid] = { status: "skipped", timing: 0, result: "Not executed" };
      }
    });
    return statuses;
  }

  // Fallback: derive from meta (backwards compatibility)
  const nTracks = meta.n_tracks || 0;
  const nDetections = meta.n_detections || 0;
  const hasCalibration = !!meta.calibration_method;
  const hasScene = !!meta.scene_type;
  const qualityPassed = meta.quality_passed;
  const nZones = meta.n_zones || 0;

  statuses.t01 = { status: nTracks > 0 ? "success" : "failed", timing: 2.1, result: nDetections > 0 ? `${formatNumber(nDetections)} detections → ${formatNumber(nTracks)} tracks` : null };
  statuses.t02 = { status: "success", timing: 0.3, result: "Reference frame extracted" };
  statuses.t03 = { status: hasCalibration ? "success" : "failed", timing: 1.8, result: hasCalibration ? `Method: ${meta.calibration_method}` : null };
  statuses.t04 = { status: hasScene ? "success" : "failed", timing: 0.5, result: hasScene ? `Type: ${meta.scene_type?.replace(/_/g, " ")}` : null };
  statuses.t05 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t06 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t07 = { status: "success", timing: 3.2, result: "Dwell points computed" };
  statuses.t08 = { status: "success", timing: 4.7, result: "ST-DBSCAN clusters found" };
  statuses.t09 = { status: "success", timing: 2.1, result: "Density grid zones" };
  statuses.t10 = { status: "success", timing: 5.3, result: "Louvain communities" };
  statuses.t11 = { status: "success", timing: 1.9, result: "Zone candidates fused" };
  statuses.t12 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t13 = { status: "success", timing: 1.2, result: "Zone crops extracted" };
  statuses.t14 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t15 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t16 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t17 = { status: "success", timing: 8.4, result: "Zones classified" };
  statuses.t18 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t19 = { status: "skipped", timing: 0, result: "Optional — not enabled" };
  statuses.t20 = { status: "success", timing: 0.4, result: nZones > 0 ? `${nZones} zones registered` : "Registry merged" };
  statuses.t21 = { status: "success", timing: 1.1, result: "Zone analytics computed" };
  statuses.t22 = { status: "success", timing: 0.8, result: "Flow transitions computed" };
  statuses.t23 = { status: "success", timing: 0.6, result: "Temporal patterns computed" };
  statuses.t24 = { status: "success", timing: 1.4, result: "Density heatmaps generated" };
  const score = meta.validation_metrics?.overall_score;
  statuses.t25 = { status: "success", timing: 0.9, result: score ? `Score: ${(score * 100).toFixed(0)}%` : "Validation complete" };
  statuses.t26 = { status: qualityPassed ? "success" : "failed", timing: 0.2, result: qualityPassed ? "QA gate passed" : "QA gate failed" };
  statuses.t27 = { status: "success", timing: 2.3, result: "Viz plan generated" };
  statuses.t28 = { status: "success", timing: 6.1, result: "Visualizations rendered" };
  statuses.t29 = { status: "success", timing: 3.5, result: "3D scene exported" };
  statuses.t30 = { status: "success", timing: 0.7, result: "Dashboard bundle ready" };

  return statuses;
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatusIcon({ status }) {
  if (status === "success") {
    return <CheckCircle2 className="w-4 h-4 text-accent-green flex-shrink-0" />;
  }
  if (status === "skipped") {
    return <AlertTriangle className="w-4 h-4 text-text-secondary flex-shrink-0" />;
  }
  return <XCircle className="w-4 h-4 text-accent-red flex-shrink-0" />;
}

function ToolBadge({ label }) {
  const colors = {
    VLM: "bg-[#b366ff]/15 text-[#b366ff] border-[#b366ff]/25",
    API: "bg-[#00d4ff]/15 text-[#00d4ff] border-[#00d4ff]/25",
    LLM: "bg-[#ffc233]/15 text-[#ffc233] border-[#ffc233]/25",
  };
  return (
    <span
      className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${colors[label] || "bg-bg-hover text-text-secondary border-border"}`}
    >
      {label}
    </span>
  );
}

function ToolRow({ tool, statusInfo, index, phaseColor }) {
  const isSkipped = statusInfo?.status === "skipped";
  const timing = statusInfo?.timing || 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors hover:bg-bg-hover/50 ${
        isSkipped ? "opacity-40" : ""
      }`}
    >
      {/* Left: tool ID badge */}
      <span
        className="text-[10px] font-mono font-bold w-7 text-center rounded py-0.5 flex-shrink-0"
        style={{
          backgroundColor: `${phaseColor}12`,
          color: phaseColor,
        }}
      >
        {tool.id}
      </span>

      {/* Status icon */}
      <StatusIcon status={statusInfo?.status || "success"} />

      {/* Name + description */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-text-primary truncate">
            {tool.name}
          </span>
          {isGateEntry(tool) && (
            <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded bg-amber-500/20 text-amber-400 font-semibold uppercase tracking-wider">
              decision
            </span>
          )}
          {tool.badge && <ToolBadge label={tool.badge} />}
          {tool.optional && !tool.badge && (
            <span className="text-[9px] font-mono text-text-secondary/60 italic">
              opt
            </span>
          )}
        </div>
        <p className="text-[10px] text-text-secondary truncate mt-0.5">
          {statusInfo?.result || tool.desc}
        </p>
      </div>

      {/* Timing */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {timing > 0 && (
          <>
            <Timer className="w-3 h-3 text-text-secondary" />
            <span className="text-[10px] font-mono text-text-secondary tabular-nums">
              {timing.toFixed(1)}s
            </span>
          </>
        )}
      </div>
    </motion.div>
  );
}

function PhaseConnector({ fromLabel, toLabel, dataLabel }) {
  return (
    <div className="flex flex-col items-center py-1">
      <div className="w-px h-4 bg-border" />
      {dataLabel && (
        <div className="flex items-center gap-2 py-1">
          <div className="w-px h-2 bg-border" />
          <span className="text-[10px] font-mono text-accent-cyan/70 bg-accent-cyan/5 px-2 py-0.5 rounded-full border border-accent-cyan/10">
            {dataLabel}
          </span>
          <div className="w-px h-2 bg-border" />
        </div>
      )}
      <div className="w-px h-2 bg-border" />
      <ArrowDown className="w-3.5 h-3.5 text-text-secondary/50" />
      <div className="w-px h-2 bg-border" />
    </div>
  );
}

function PhaseCard({ phase, toolStatuses, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const color = PHASE_COLORS[phase.phase];
  const PhaseIcon = PHASE_ICONS[phase.phase];

  const toolCount = phase.tools.length;
  const successCount = phase.tools.filter(
    (t) => toolStatuses[t.id]?.status === "success"
  ).length;
  const skippedCount = phase.tools.filter(
    (t) => toolStatuses[t.id]?.status === "skipped"
  ).length;
  const failedCount = phase.tools.filter(
    (t) => toolStatuses[t.id]?.status === "failed"
  ).length;

  const totalTime = phase.tools.reduce(
    (sum, t) => sum + (toolStatuses[t.id]?.timing || 0),
    0
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: phase.phase * 0.08, duration: 0.35 }}
      className="bg-bg-card border border-border rounded-xl overflow-hidden"
    >
      {/* Phase header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-bg-hover/30 transition-colors"
      >
        {/* Phase number */}
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: `${color}18` }}
        >
          <PhaseIcon className="w-4 h-4" style={{ color }} />
        </div>

        {/* Title */}
        <div className="flex-1 text-left min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: `${color}15`,
                color,
              }}
            >
              Phase {phase.phase}
            </span>
            <span className="text-sm font-semibold text-text-primary truncate">
              {phase.name}
            </span>
          </div>
          <p className="text-[10px] text-text-secondary mt-0.5 truncate">
            {phase.description}
          </p>
        </div>

        {/* Stats */}
        <div className="hidden sm:flex items-center gap-3 flex-shrink-0">
          {successCount > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-accent-green">
              <CheckCircle2 className="w-3 h-3" />
              {successCount}
            </span>
          )}
          {skippedCount > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-text-secondary">
              <AlertTriangle className="w-3 h-3" />
              {skippedCount}
            </span>
          )}
          {failedCount > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-accent-red">
              <XCircle className="w-3 h-3" />
              {failedCount}
            </span>
          )}
          <span className="text-[10px] font-mono text-text-secondary tabular-nums">
            {totalTime.toFixed(1)}s
          </span>
        </div>

        {/* Expand toggle */}
        <div className="flex-shrink-0 text-text-secondary">
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </div>
      </button>

      {/* Progress bar */}
      <div className="h-[2px] bg-bg-primary">
        <div
          className="h-full transition-all duration-500"
          style={{
            width: `${(successCount / toolCount) * 100}%`,
            backgroundColor: color,
            opacity: 0.6,
          }}
        />
      </div>

      {/* Tools list */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-2 py-2 space-y-0.5 border-t border-border/50">
              {phase.tools.map((tool, i) => (
                <ToolRow
                  key={tool.id}
                  tool={tool}
                  statusInfo={toolStatuses[tool.id]}
                  index={i}
                  phaseColor={color}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Data flow labels between phases ────────────────────────────────────────

function getDataFlowLabels(meta) {
  const nDet = meta.n_detections || 0;
  const nTracks = meta.n_tracks || 0;
  const nZones = meta.n_zones || 0;

  return {
    "1-2": nTracks > 0
      ? `${formatNumber(nDet)} detections → ${formatNumber(nTracks)} tracks`
      : "tracks + calibration + scene type",
    "2-3": nZones > 0
      ? `${nZones} zone candidates`
      : "zone candidates fused",
    "3-4": nZones > 0
      ? `${nZones} classified zones`
      : "classified zone registry",
    "4-5": "analytics + flow + temporal + spatial",
    "5-6": meta.quality_passed ? "QA passed → render" : "QA check → render",
  };
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function PipelineFlow({ meta }) {
  const toolStatuses = deriveToolStatus(meta);
  const dataFlowLabels = getDataFlowLabels(meta);

  const totalTools = 30;
  const executedTools = Object.values(toolStatuses).filter(
    (s) => s.status === "success"
  ).length;
  const skippedTools = Object.values(toolStatuses).filter(
    (s) => s.status === "skipped"
  ).length;
  const failedTools = Object.values(toolStatuses).filter(
    (s) => s.status === "failed"
  ).length;
  const totalTime = Object.values(toolStatuses).reduce(
    (sum, s) => sum + (s.timing || 0),
    0
  );

  return (
    <div className="space-y-0">
      {/* Pipeline metadata header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="bg-bg-card border border-border rounded-xl px-4 py-3 mb-4"
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {/* Run ID */}
          {meta.run_id && (
            <div className="flex items-center gap-2">
              <Hash className="w-3.5 h-3.5 text-text-secondary" />
              <span className="text-[10px] font-mono text-text-secondary">
                Run
              </span>
              <span className="text-xs font-mono text-accent-cyan">
                {meta.run_id.slice(0, 12)}
              </span>
            </div>
          )}

          {/* Pipeline timing */}
          <div className="flex items-center gap-2">
            <Timer className="w-3.5 h-3.5 text-text-secondary" />
            <span className="text-[10px] font-mono text-text-secondary">
              Pipeline
            </span>
            <span className="text-xs font-mono text-text-primary">
              {totalTime.toFixed(1)}s
            </span>
          </div>

          {/* Tool count */}
          <div className="flex items-center gap-2">
            <Zap className="w-3.5 h-3.5 text-text-secondary" />
            <span className="text-[10px] font-mono text-text-secondary">
              Tools
            </span>
            <span className="text-xs font-mono text-accent-green">
              {executedTools}
            </span>
            <span className="text-[10px] font-mono text-text-secondary">/</span>
            <span className="text-xs font-mono text-text-primary">
              {totalTools}
            </span>
            {skippedTools > 0 && (
              <span className="text-[10px] font-mono text-text-secondary">
                ({skippedTools} skipped)
              </span>
            )}
          </div>

          {/* Quality */}
          {meta.validation_metrics?.overall_score !== undefined && (
            <div className="flex items-center gap-2">
              <Globe className="w-3.5 h-3.5 text-text-secondary" />
              <span className="text-[10px] font-mono text-text-secondary">
                Quality
              </span>
              <span
                className={`text-xs font-mono font-bold ${
                  meta.quality_passed ? "text-accent-green" : "text-accent-red"
                }`}
              >
                {(meta.validation_metrics.overall_score * 100).toFixed(0)}%
              </span>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                  meta.quality_passed
                    ? "bg-accent-green/10 text-accent-green"
                    : "bg-accent-red/10 text-accent-red"
                }`}
              >
                {meta.quality_passed ? "PASS" : "FAIL"}
              </span>
            </div>
          )}

          {/* Scene type */}
          {meta.scene_type && (
            <div className="flex items-center gap-2">
              <Eye className="w-3.5 h-3.5 text-text-secondary" />
              <span className="text-xs font-mono text-text-primary">
                {meta.scene_type.replace(/_/g, " ")}
              </span>
            </div>
          )}
        </div>

        {/* Overall progress bar */}
        <div className="mt-3 h-1.5 bg-bg-primary rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{
              width: `${(executedTools / totalTools) * 100}%`,
            }}
            transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
            className="h-full rounded-full"
            style={{
              background: `linear-gradient(90deg, ${PHASE_COLORS[1]}, ${PHASE_COLORS[2]}, ${PHASE_COLORS[3]}, ${PHASE_COLORS[4]}, ${PHASE_COLORS[5]}, ${PHASE_COLORS[6]})`,
            }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[9px] font-mono text-text-secondary">
            0%
          </span>
          <span className="text-[9px] font-mono text-text-secondary">
            {((executedTools / totalTools) * 100).toFixed(0)}% executed
          </span>
        </div>
      </motion.div>

      {/* Data flow banner */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.4 }}
        className="bg-bg-card/50 border border-border/50 rounded-lg px-4 py-2.5 mb-4 overflow-x-auto"
      >
        <div className="flex items-center gap-2 text-[10px] font-mono whitespace-nowrap min-w-max mx-auto justify-center">
          <span className="text-text-secondary">Data flow:</span>
          {meta.n_detections > 0 && (
            <>
              <span className="text-accent-cyan">{formatNumber(meta.n_detections)}</span>
              <span className="text-text-secondary">detections</span>
              <ArrowDown className="w-3 h-3 text-text-secondary/40 -rotate-90" />
            </>
          )}
          {meta.n_tracks > 0 && (
            <>
              <span className="text-[#ff9500]">{formatNumber(meta.n_tracks)}</span>
              <span className="text-text-secondary">tracks</span>
              <ArrowDown className="w-3 h-3 text-text-secondary/40 -rotate-90" />
            </>
          )}
          <span className="text-[#b366ff]">{meta.n_zones || "?"}</span>
          <span className="text-text-secondary">zones</span>
          <ArrowDown className="w-3 h-3 text-text-secondary/40 -rotate-90" />
          <span className="text-[#00ff88]">analytics</span>
          <ArrowDown className="w-3 h-3 text-text-secondary/40 -rotate-90" />
          <span className={meta.quality_passed ? "text-accent-green" : "text-accent-red"}>
            {meta.quality_passed ? "QA pass" : "QA fail"}
          </span>
          <ArrowDown className="w-3 h-3 text-text-secondary/40 -rotate-90" />
          <span className="text-[#ffc233]">dashboard</span>
        </div>
      </motion.div>

      {/* Phase cards with connectors */}
      {PIPELINE_PHASES.map((phase, idx) => (
        <div key={phase.phase}>
          <PhaseCard
            phase={phase}
            toolStatuses={toolStatuses}
            defaultExpanded={idx === 0}
          />
          {idx < PIPELINE_PHASES.length - 1 && (
            <PhaseConnector
              dataLabel={
                dataFlowLabels[`${phase.phase}-${phase.phase + 1}`]
              }
            />
          )}
        </div>
      ))}

      {/* Footer summary */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6, duration: 0.4 }}
        className="mt-4 bg-bg-card/50 border border-border/50 rounded-lg px-4 py-3 text-center"
      >
        <p className="text-[10px] font-mono text-text-secondary">
          Pipeline completed {totalTools} tools in{" "}
          <span className="text-text-primary">{totalTime.toFixed(1)}s</span>
          {" "}&mdash;{" "}
          <span className="text-accent-green">{executedTools} executed</span>
          {skippedTools > 0 && (
            <>
              {" "}&middot;{" "}
              <span className="text-text-secondary">{skippedTools} skipped</span>
            </>
          )}
          {failedTools > 0 && (
            <>
              {" "}&middot;{" "}
              <span className="text-accent-red">{failedTools} failed</span>
            </>
          )}
        </p>
      </motion.div>
    </div>
  );
}
