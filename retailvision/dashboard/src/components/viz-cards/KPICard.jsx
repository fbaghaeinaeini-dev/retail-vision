import { useMemo } from "react";
import { formatDuration } from "../../lib/colors";

export default function KPICard({ config, report }) {
  const vlmMetrics = config?.metrics || null;

  const computed = useMemo(() => {
    const zones = report?.zones || {};
    const analytics = report?.analytics || {};
    const zoneCount = Object.keys(zones).length;

    let totalVisits = 0;
    let totalDwell = 0;
    let dwellCount = 0;
    let peakDensity = 0;

    for (const zid of Object.keys(analytics)) {
      const a = analytics[zid];
      totalVisits += a?.total_visits || 0;
      if (a?.avg_dwell_seconds > 0) {
        totalDwell += a.avg_dwell_seconds;
        dwellCount++;
      }
      peakDensity = Math.max(peakDensity, a?.density_people_per_m2_hr || 0);
    }

    const avgDwell = dwellCount > 0 ? totalDwell / dwellCount : 0;

    return {
      total_zones: { label: "Total Zones", value: String(zoneCount) },
      total_visits: { label: "Total Visits", value: String(totalVisits) },
      avg_dwell: { label: "Avg Dwell", value: formatDuration(avgDwell) },
      peak_density: {
        label: "Peak Density",
        value: `${peakDensity.toFixed(1)}/m\u00B2/hr`,
      },
    };
  }, [report]);

  // VLM-provided metrics: render directly
  if (vlmMetrics && Array.isArray(vlmMetrics) && vlmMetrics.length > 0) {
    return (
      <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
        <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
            {config?.title || "Key Metrics"}
          </h4>
        </div>
        <div className="p-3">
          <div className="grid grid-cols-2 gap-2">
            {vlmMetrics.map((m, i) => (
              <div
                key={i}
                className="bg-[#0a0a12] rounded px-2.5 py-2 border border-border/50"
              >
                <p className="text-[8px] text-text-secondary uppercase tracking-wider font-semibold mb-0.5">
                  {m.label}
                </p>
                <p className="text-lg font-mono font-bold text-accent-cyan tabular-nums">
                  {m.value}
                  {m.unit && (
                    <span className="text-[9px] text-text-secondary font-normal ml-1">
                      {m.unit}
                    </span>
                  )}
                </p>
                {m.description && (
                  <p className="text-[8px] text-text-secondary mt-0.5 truncate">
                    {m.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Existing behavior: compute from report
  const requestedMetrics = config?.metrics || null;
  const defaultKeys = ["total_zones", "total_visits", "avg_dwell", "peak_density"];
  const displayKeys = requestedMetrics || defaultKeys;

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {config?.title || "Key Metrics"}
        </h4>
      </div>
      <div className="p-3">
        <div className="grid grid-cols-2 gap-2">
          {displayKeys.map((key) => {
            const metric = computed[key];
            if (!metric) return null;
            return (
              <div
                key={key}
                className="bg-[#0a0a12] rounded px-2.5 py-2 border border-border/50"
              >
                <p className="text-[8px] text-text-secondary uppercase tracking-wider font-semibold mb-0.5">
                  {metric.label}
                </p>
                <p className="text-lg font-mono font-bold text-accent-cyan tabular-nums">
                  {metric.value}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
