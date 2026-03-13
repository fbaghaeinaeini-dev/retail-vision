import { useState } from "react";

export default function HeatmapImageCard({ config, report, onZoneClick }) {
  const [error, setError] = useState(false);
  const title = config?.title || "Detection Heatmap";

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h4>
      </div>
      <div className="p-2">
        {!error ? (
          <img
            src="/data/viz/detection_heatmap.png"
            alt="Detection heatmap"
            className="w-full h-auto rounded object-contain"
            style={{ maxHeight: 220 }}
            onError={() => setError(true)}
          />
        ) : (
          <div className="flex items-center justify-center h-32 bg-[#0a0a12] rounded border border-border/50">
            <p className="text-text-secondary text-xs font-mono">
              Heatmap image not available
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
