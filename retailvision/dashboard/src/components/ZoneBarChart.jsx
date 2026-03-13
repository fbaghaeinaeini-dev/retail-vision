import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { getZoneColor, formatDuration } from "../lib/colors";

/**
 * Bar chart comparing zone metrics (visits, dwell time, density).
 */
export default function ZoneBarChart({ analytics, zones }) {
  const data = Object.entries(analytics)
    .map(([zid, a]) => ({
      zoneId: zid,
      name: (zones[zid]?.business_name || zid).slice(0, 12),
      type: zones[zid]?.zone_type || "unknown",
      visits: a?.total_visits || 0,
      avgDwell: a?.avg_dwell_seconds || 0,
      density: a?.density_people_per_m2_hr || 0,
    }))
    .sort((a, b) => b.visits - a.visits);

  if (!data.length) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-6 text-center">
        <p className="text-text-secondary text-sm">No analytics data</p>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-bg-card border border-border rounded-lg p-3 text-xs font-mono shadow-xl">
        <p className="text-text-primary font-semibold mb-1">{d.name}</p>
        <p className="text-text-secondary">Visits: {d.visits}</p>
        <p className="text-text-secondary">Avg Dwell: {formatDuration(d.avgDwell)}</p>
        <p className="text-text-secondary">Density: {d.density.toFixed(1)}/m²/hr</p>
      </div>
    );
  };

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Zone Comparison
        </h3>
      </div>
      <div className="p-4" style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <XAxis
              dataKey="name"
              tick={{ fill: "#6e6e82", fontSize: 10, fontFamily: "DM Sans" }}
              axisLine={{ stroke: "#1e1e2e" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#6e6e82", fontSize: 10, fontFamily: "JetBrains Mono" }}
              axisLine={{ stroke: "#1e1e2e" }}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
            <Bar dataKey="visits" radius={[4, 4, 0, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={getZoneColor(d.type)} fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
