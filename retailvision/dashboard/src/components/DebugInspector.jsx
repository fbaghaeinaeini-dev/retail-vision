import { useState } from "react";
import { motion } from "framer-motion";
import { X, ChevronDown, ChevronRight } from "lucide-react";

/**
 * Debug inspector: raw JSON viewer for the report data.
 * Shows pipeline metadata, tool history, and raw zone data.
 */
export default function DebugInspector({ report, onClose }) {
  return (
    <motion.div
      initial={{ y: "100%" }}
      animate={{ y: 0 }}
      exit={{ y: "100%" }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className="fixed bottom-0 left-0 right-0 h-[50vh] bg-bg-card border-t border-border z-50 flex flex-col"
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-accent-amber">
          Debug Inspector
        </h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-bg-hover transition-colors">
          <X className="w-4 h-4 text-text-secondary" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs">
        <Collapsible title="Pipeline Meta" defaultOpen>
          <JsonBlock data={report.meta} />
        </Collapsible>

        <Collapsible title={`Zones (${Object.keys(report.zones || {}).length})`}>
          <JsonBlock data={report.zones} />
        </Collapsible>

        <Collapsible title="Analytics">
          <JsonBlock data={report.analytics} />
        </Collapsible>

        <Collapsible title="Flow">
          <JsonBlock data={report.flow} />
        </Collapsible>

        <Collapsible title="Temporal">
          <JsonBlock data={report.temporal} />
        </Collapsible>

        <Collapsible title="Spatial">
          {/* Skip heatmap_density as it's huge */}
          <JsonBlock
            data={{
              ...report.spatial,
              heatmap_density: report.spatial?.heatmap_density
                ? `[${report.spatial.heatmap_density.length} rows]`
                : undefined,
            }}
          />
        </Collapsible>

        <Collapsible title="Visualization Plan">
          <JsonBlock data={report.visualization_plan} />
        </Collapsible>
      </div>
    </motion.div>
  );
}

function Collapsible({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-text-primary hover:text-accent-cyan transition-colors mb-1"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        <span className="text-[11px] font-semibold">{title}</span>
      </button>
      {open && <div className="ml-4">{children}</div>}
    </div>
  );
}

function JsonBlock({ data }) {
  if (!data) return <span className="text-text-secondary">null</span>;

  const text = JSON.stringify(data, null, 2);
  // Truncate very long JSON
  const display = text.length > 5000 ? text.slice(0, 5000) + "\n... (truncated)" : text;

  return (
    <pre className="bg-bg-primary rounded p-2 overflow-x-auto text-[10px] leading-relaxed text-text-secondary whitespace-pre-wrap">
      {display}
    </pre>
  );
}
