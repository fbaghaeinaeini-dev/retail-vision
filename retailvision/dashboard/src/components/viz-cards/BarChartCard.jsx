import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { formatDuration } from "../../lib/colors";

/**
 * Distinct color palette — each bar gets its own color by index.
 */
const BAR_PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444",
  "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#a855f7",
  "#eab308", "#6366f1", "#22c55e", "#e11d48", "#0ea5e9",
];

const METRIC_LABELS = {
  total_visits: "Visits",
  avg_dwell_seconds: "Avg Dwell (s)",
  density_people_per_m2_hr: "Density (/m²/hr)",
};

export default function BarChartCard({ config, report, onZoneClick }) {
  const metric = config?.metric || "total_visits";
  const filterZones = config?.zones || null;
  const sortBy = config?.sort_by || metric;
  const limit = config?.limit || null;
  const title = config?.title || null;
  const vlmData = config?.data || null;

  const data = useMemo(() => {
    // VLM-provided data: use directly
    if (vlmData && Array.isArray(vlmData) && vlmData.length > 0) {
      const items = vlmData.map((d) => ({
        zoneId: d.zone_id || null,
        name: (d.label || d.zone_id || "Unknown").slice(0, 16),
        type: d.type || "unknown",
        value: d.value ?? 0,
      }));
      return limit ? items.slice(0, limit) : items;
    }

    // Compute from report (existing behavior)
    if (!report?.analytics || !report?.zones) return [];

    const entries = Object.entries(report.analytics)
      .filter(([zid]) => !filterZones || filterZones.includes(zid))
      .map(([zid, a]) => ({
        zoneId: zid,
        name: (report.zones[zid]?.business_name || zid).slice(0, 12),
        type: report.zones[zid]?.zone_type || "unknown",
        total_visits: a?.total_visits || 0,
        avg_dwell_seconds: a?.avg_dwell_seconds || 0,
        density_people_per_m2_hr: a?.density_people_per_m2_hr || 0,
      }));

    const key = entries.length > 0 && sortBy in entries[0] ? sortBy : metric;
    const sorted = entries.sort((a, b) => b[key] - a[key]);
    return limit ? sorted.slice(0, limit) : sorted;
  }, [report, metric, filterZones, sortBy, vlmData, limit]);

  // Determine the data key for the bar
  const barDataKey = vlmData ? "value" : metric;

  if (!data.length) {
    return (
      <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
        <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
            {title || "Bar Chart"}
          </h4>
        </div>
        <div className="p-3 text-center">
          <p className="text-text-secondary text-xs">No analytics data</p>
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;

    // VLM-provided data tooltip
    if (vlmData) {
      return (
        <div className="bg-bg-card border border-border rounded-lg p-2 text-[10px] font-mono shadow-xl">
          <p className="text-text-primary font-semibold mb-0.5">{d.name}</p>
          <p className="text-text-secondary">Value: {d.value}</p>
        </div>
      );
    }

    return (
      <div className="bg-bg-card border border-border rounded-lg p-2 text-[10px] font-mono shadow-xl">
        <p className="text-text-primary font-semibold mb-0.5">{d.name}</p>
        <p className="text-text-secondary">Visits: {d.total_visits}</p>
        <p className="text-text-secondary">Dwell: {formatDuration(d.avg_dwell_seconds)}</p>
        <p className="text-text-secondary">Density: {d.density_people_per_m2_hr.toFixed(1)}/m²/hr</p>
      </div>
    );
  };

  const formatValue = (v) => {
    if (vlmData) return v;
    if (metric === "avg_dwell_seconds") return formatDuration(v);
    if (metric === "density_people_per_m2_hr") return v.toFixed(1);
    return v;
  };

  const handleBarClick = (entry) => {
    if (onZoneClick && entry?.zoneId) {
      onZoneClick(entry.zoneId);
    }
  };

  const headerLabel = title || METRIC_LABELS[metric] || metric;

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {headerLabel}
        </h4>
        <span className="text-[9px] font-mono text-text-secondary">
          {data.length} zones
        </span>
      </div>
      <div className="p-3" style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <XAxis
              dataKey="name"
              tick={{ fill: "#6e6e82", fontSize: 9, fontFamily: "DM Sans" }}
              axisLine={{ stroke: "#1e1e2e" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#6e6e82", fontSize: 9, fontFamily: "JetBrains Mono" }}
              axisLine={{ stroke: "#1e1e2e" }}
              tickLine={false}
              tickFormatter={formatValue}
              width={40}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
            <Bar
              dataKey={barDataKey}
              radius={[3, 3, 0, 0]}
              onClick={handleBarClick}
              style={{ cursor: onZoneClick ? "pointer" : "default" }}
            >
              {data.map((d, i) => (
                <Cell key={i} fill={BAR_PALETTE[i % BAR_PALETTE.length]} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
