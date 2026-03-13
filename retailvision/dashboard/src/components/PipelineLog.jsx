import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Filter,
  ChevronDown,
  ChevronRight,
  Terminal,
  Layers,
  Zap,
  Search,
} from "lucide-react";

// ─── Phase metadata ──────────────────────────────────────────────────────────

const PHASE_META = {
  1: { name: "Scene Understanding", color: "#00d4ff", icon: "eye" },
  2: { name: "Zone Discovery", color: "#ff9500", icon: "layers" },
  3: { name: "Zone Classification", color: "#b366ff", icon: "cpu" },
  4: { name: "Analytics", color: "#00ff88", icon: "chart" },
  5: { name: "Validation", color: "#ff3366", icon: "shield" },
  6: { name: "Visualization", color: "#ffc233", icon: "layout" },
};

// ─── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({ success, duration }) {
  if (success) {
    return (
      <div className="flex items-center gap-1.5">
        <CheckCircle2 className="w-3.5 h-3.5 text-accent-green" />
        <span className="text-[10px] font-mono text-accent-green font-bold">
          OK
        </span>
        {duration > 0 && (
          <span className="text-[10px] font-mono text-text-secondary ml-1 tabular-nums">
            {duration.toFixed(1)}s
          </span>
        )}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5">
      <XCircle className="w-3.5 h-3.5 text-accent-red" />
      <span className="text-[10px] font-mono text-accent-red font-bold">
        FAIL
      </span>
    </div>
  );
}

// ─── Single log entry ────────────────────────────────────────────────────────

function LogEntry({ entry, index, expanded, onToggle }) {
  const phase = PHASE_META[entry.phase] || PHASE_META[1];
  const hasMessage = entry.message && entry.message.length > 0;
  const isGate = entry.is_gate || entry.tool?.startsWith('gate');

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.02, duration: 0.2 }}
      className="group"
    >
      {/* Main row */}
      <button
        onClick={onToggle}
        className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-bg-hover/40 transition-colors rounded-lg text-left ${isGate ? 'border-l-2 border-amber-500 pl-2 bg-amber-500/5' : ''}`}
      >
        {/* Step number */}
        <span className="text-[10px] font-mono text-text-secondary/60 w-6 text-right tabular-nums flex-shrink-0">
          {String(index + 1).padStart(2, "0")}
        </span>

        {/* Phase dot */}
        <div
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: phase.color }}
        />

        {/* Vertical connector line */}
        <div className="relative flex-shrink-0 w-0">
          <div
            className="absolute left-[-9px] top-4 w-px h-6 opacity-20"
            style={{ backgroundColor: phase.color }}
          />
        </div>

        {/* Tool name */}
        <span className="text-xs font-mono text-text-primary flex-shrink-0 min-w-[220px]">
          {isGate && <span className="text-amber-400 text-xs font-bold mr-1">DECISION</span>}
          {entry.tool}
        </span>

        {/* Phase label */}
        <span
          className="text-[9px] font-mono px-1.5 py-0.5 rounded flex-shrink-0"
          style={{
            backgroundColor: `${phase.color}12`,
            color: phase.color,
          }}
        >
          P{entry.phase}
        </span>

        {/* Message preview */}
        <span className="text-[11px] text-text-secondary truncate flex-1 min-w-0">
          {entry.message || "—"}
        </span>

        {/* Status */}
        <div className="flex-shrink-0">
          <StatusBadge success={entry.success} duration={entry.duration} />
        </div>

        {/* Expand toggle */}
        <div className="flex-shrink-0 text-text-secondary/40 group-hover:text-text-secondary transition-colors">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </div>
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && hasMessage && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="ml-14 mr-4 mb-2 bg-bg-primary/50 border border-border/30 rounded-lg px-3 py-2">
              <div className="flex items-start gap-2">
                <Terminal className="w-3 h-3 text-text-secondary/50 mt-0.5 flex-shrink-0" />
                <pre className="text-[11px] font-mono text-text-secondary whitespace-pre-wrap break-all leading-relaxed">
                  {entry.message}
                </pre>
              </div>
              <div className="flex items-center gap-4 mt-2 pt-2 border-t border-border/20">
                <span className="text-[9px] font-mono text-text-secondary/50">
                  Phase {entry.phase}: {phase.name}
                </span>
                <span className="text-[9px] font-mono text-text-secondary/50">
                  Duration: {(entry.duration || 0).toFixed(2)}s
                </span>
                <span
                  className="text-[9px] font-mono"
                  style={{ color: entry.success ? "#00ff88" : "#ff3366" }}
                >
                  {entry.success ? "SUCCESS" : "FAILED"}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Phase summary bar ───────────────────────────────────────────────────────

function PhaseSummaryBar({ history }) {
  const phases = useMemo(() => {
    const grouped = {};
    for (const entry of history) {
      if (!grouped[entry.phase]) {
        grouped[entry.phase] = { tools: 0, ok: 0, fail: 0, totalTime: 0 };
      }
      grouped[entry.phase].tools++;
      if (entry.success) grouped[entry.phase].ok++;
      else grouped[entry.phase].fail++;
      grouped[entry.phase].totalTime += entry.duration || 0;
    }
    return grouped;
  }, [history]);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {Object.entries(phases).map(([phase, data]) => {
        const meta = PHASE_META[phase] || PHASE_META[1];
        return (
          <div
            key={phase}
            className="flex items-center gap-1.5 bg-bg-card border border-border/50 rounded-lg px-2.5 py-1.5"
          >
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: meta.color }}
            />
            <span
              className="text-[10px] font-mono font-bold"
              style={{ color: meta.color }}
            >
              P{phase}
            </span>
            <span className="text-[10px] font-mono text-text-secondary">
              {data.ok}/{data.tools}
            </span>
            <span className="text-[9px] font-mono text-text-secondary/50">
              {data.totalTime.toFixed(1)}s
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Timeline bar ────────────────────────────────────────────────────────────

function TimelineBar({ history }) {
  const totalTime = history.reduce((sum, e) => sum + (e.duration || 0), 0);
  if (totalTime === 0) return null;

  return (
    <div className="bg-bg-card border border-border rounded-xl p-3">
      <div className="flex items-center gap-2 mb-2">
        <Clock className="w-3.5 h-3.5 text-text-secondary" />
        <span className="text-[10px] font-mono text-text-secondary">
          Execution Timeline
        </span>
        <span className="text-[10px] font-mono text-text-primary ml-auto tabular-nums">
          {totalTime.toFixed(1)}s total
        </span>
      </div>
      <div className="flex h-5 rounded-md overflow-hidden bg-bg-primary">
        {history.map((entry, i) => {
          const pct = ((entry.duration || 0) / totalTime) * 100;
          if (pct < 0.5) return null;
          const phase = PHASE_META[entry.phase] || PHASE_META[1];
          return (
            <div
              key={i}
              className="relative group cursor-pointer transition-opacity hover:opacity-80"
              style={{
                width: `${pct}%`,
                backgroundColor: entry.success ? phase.color : "#ff3366",
                opacity: 0.7,
              }}
              title={`${entry.tool}: ${(entry.duration || 0).toFixed(1)}s`}
            >
              {pct > 8 && (
                <span className="absolute inset-0 flex items-center justify-center text-[8px] font-mono text-white/80 truncate px-1">
                  {entry.tool.replace(/^(compute_|vlm_|strategy_|render_|export_)/, "")}
                </span>
              )}
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex items-center gap-3 mt-2 flex-wrap">
        {Object.entries(PHASE_META).map(([p, meta]) => (
          <div key={p} className="flex items-center gap-1">
            <div
              className="w-2 h-2 rounded-sm"
              style={{ backgroundColor: meta.color, opacity: 0.7 }}
            />
            <span className="text-[9px] font-mono text-text-secondary/60">
              {meta.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function PipelineLog({ meta }) {
  const history = meta?.tool_history || [];
  const [expandedIdx, setExpandedIdx] = useState(null);
  const [filterPhase, setFilterPhase] = useState(null);
  const [filterStatus, setFilterStatus] = useState(null); // null | "success" | "failed"
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = useMemo(() => {
    return history.filter((entry) => {
      if (filterPhase && entry.phase !== filterPhase) return false;
      if (filterStatus === "success" && !entry.success) return false;
      if (filterStatus === "failed" && entry.success) return false;
      if (
        searchQuery &&
        !entry.tool.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !(entry.message || "").toLowerCase().includes(searchQuery.toLowerCase())
      )
        return false;
      return true;
    });
  }, [history, filterPhase, filterStatus, searchQuery]);

  const totalTime = history.reduce((sum, e) => sum + (e.duration || 0), 0);
  const okCount = history.filter((e) => e.success).length;
  const failCount = history.filter((e) => !e.success).length;

  if (history.length === 0) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-8 text-center">
        <Terminal className="w-8 h-8 text-text-secondary/30 mx-auto mb-3" />
        <p className="text-text-secondary text-sm">
          No pipeline execution log available.
        </p>
        <p className="text-text-secondary/60 text-xs mt-1">
          Run the pipeline to generate tool_history in report.json
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-bg-card border border-border rounded-xl px-4 py-3"
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mb-3">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-accent-cyan" />
            <span className="text-sm font-semibold text-text-primary">
              Execution Log
            </span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-mono">
            <span className="text-text-secondary">
              <span className="text-text-primary">{history.length}</span> tools
            </span>
            <span className="text-accent-green">
              {okCount} passed
            </span>
            {failCount > 0 && (
              <span className="text-accent-red">{failCount} failed</span>
            )}
            <span className="text-text-secondary">
              {totalTime.toFixed(1)}s total
            </span>
          </div>
        </div>
        <PhaseSummaryBar history={history} />
      </motion.div>

      {/* Timeline */}
      <TimelineBar history={history} />

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-secondary/50" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter tools..."
            className="bg-bg-card border border-border rounded-lg pl-8 pr-3 py-1.5 text-[11px] font-mono text-text-primary placeholder:text-text-secondary/40 w-48 focus:outline-none focus:border-accent-cyan/50"
          />
        </div>

        {/* Phase filter */}
        <div className="flex items-center gap-1">
          <Filter className="w-3 h-3 text-text-secondary/50" />
          <button
            onClick={() => setFilterPhase(null)}
            className={`text-[10px] font-mono px-2 py-1 rounded transition-colors ${
              !filterPhase
                ? "bg-accent-cyan/15 text-accent-cyan"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            All
          </button>
          {[1, 2, 3, 4, 5, 6].map((p) => {
            const meta = PHASE_META[p];
            return (
              <button
                key={p}
                onClick={() => setFilterPhase(filterPhase === p ? null : p)}
                className="text-[10px] font-mono px-2 py-1 rounded transition-colors"
                style={{
                  backgroundColor:
                    filterPhase === p ? `${meta.color}20` : "transparent",
                  color: filterPhase === p ? meta.color : undefined,
                }}
              >
                P{p}
              </button>
            );
          })}
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={() =>
              setFilterStatus(filterStatus === "success" ? null : "success")
            }
            className={`flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded transition-colors ${
              filterStatus === "success"
                ? "bg-accent-green/15 text-accent-green"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <CheckCircle2 className="w-3 h-3" />
            OK
          </button>
          <button
            onClick={() =>
              setFilterStatus(filterStatus === "failed" ? null : "failed")
            }
            className={`flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded transition-colors ${
              filterStatus === "failed"
                ? "bg-accent-red/15 text-accent-red"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <XCircle className="w-3 h-3" />
            Fail
          </button>
        </div>

        {/* Count */}
        <span className="text-[10px] font-mono text-text-secondary/50 ml-auto">
          {filtered.length} / {history.length} shown
        </span>
      </div>

      {/* Log entries */}
      <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-3 py-2 bg-bg-hover/30 border-b border-border/50">
          <span className="text-[9px] font-mono text-text-secondary/50 w-6 text-right">
            #
          </span>
          <span className="w-2" />
          <span className="text-[9px] font-mono text-text-secondary/50 min-w-[220px]">
            TOOL
          </span>
          <span className="text-[9px] font-mono text-text-secondary/50 w-8">
            PH
          </span>
          <span className="text-[9px] font-mono text-text-secondary/50 flex-1">
            OUTPUT
          </span>
          <span className="text-[9px] font-mono text-text-secondary/50 w-20 text-right">
            STATUS
          </span>
          <span className="w-4" />
        </div>

        {/* Entries */}
        <div className="divide-y divide-border/20">
          {filtered.map((entry, idx) => {
            const originalIdx = history.indexOf(entry);
            return (
              <LogEntry
                key={originalIdx}
                entry={entry}
                index={originalIdx}
                expanded={expandedIdx === originalIdx}
                onToggle={() =>
                  setExpandedIdx(
                    expandedIdx === originalIdx ? null : originalIdx
                  )
                }
              />
            );
          })}
        </div>

        {filtered.length === 0 && (
          <div className="px-4 py-8 text-center">
            <p className="text-text-secondary/50 text-xs font-mono">
              No matching log entries
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
