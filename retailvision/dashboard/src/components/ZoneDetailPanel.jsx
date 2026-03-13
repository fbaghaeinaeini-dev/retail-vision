import { useState } from "react";
import { motion } from "framer-motion";
import {
  X,
  MapPin,
  Clock,
  Users,
  TrendingUp,
  Package,
  Type,
  Layers,
  BarChart3,
} from "lucide-react";
import { getZoneColor, formatDuration, formatZoneTypeLabel } from "../lib/colors";

const STRATEGY_COLORS = {
  occupancy_grid: "#00d4ff",
  trajectory_graph: "#ff9500",
  dwell_clustering: "#b366ff",
  scene_graph: "#00ff88",
  clustering: "#b366ff",
  spatial_analysis: "#ffc233",
  vlm: "#ff3366",
  vlm_detect_structures: "#ff3366",
};

/**
 * Slide-in detail panel for a selected zone.
 * Shows zone crop image, metrics with mini sparklines,
 * and contributing strategies with colored pills.
 */
export default function ZoneDetailPanel({
  zoneId,
  zone,
  analytics,
  temporal,
  onClose,
}) {
  if (!zone) return null;

  const color = getZoneColor(zone.zone_type);
  const a = analytics || {};
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Get temporal data for mini sparkline
  const occupancyData = temporal?.occupancy_matrix?.[zoneId] || [];
  const maxOcc = occupancyData.length
    ? Math.max(...occupancyData, 1)
    : 1;

  return (
    <motion.div
      initial={{ x: 400, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 400, opacity: 0 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className="fixed top-14 right-0 bottom-0 w-[400px] bg-bg-card border-l border-border z-40 overflow-y-auto"
    >
      {/* Header */}
      <div className="sticky top-0 bg-bg-card/95 backdrop-blur-sm border-b border-border p-4 z-10">
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: color }}
              />
              <h2 className="text-base font-semibold truncate">
                {zone.business_name || zoneId}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                style={{
                  backgroundColor: `${color}20`,
                  color: color,
                }}
              >
                {formatZoneTypeLabel(zone.zone_type)}
              </span>
              <span className="text-[10px] text-text-secondary font-mono">
                {zoneId}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-bg-hover transition-colors ml-2"
          >
            <X className="w-4 h-4 text-text-secondary" />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Zone crop image */}
        {!imageError && (
          <div className="rounded-lg overflow-hidden bg-bg-primary border border-border">
            <img
              src={`/data/zones/${zoneId}_crop.png`}
              alt={`Zone ${zoneId} crop`}
              className={`w-full h-auto transition-opacity ${imageLoaded ? "opacity-100" : "opacity-0"}`}
              style={{ maxHeight: 180 }}
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageError(true)}
            />
            {!imageLoaded && !imageError && (
              <div className="h-20 flex items-center justify-center">
                <span className="text-[10px] text-text-secondary font-mono">
                  Loading crop...
                </span>
              </div>
            )}
          </div>
        )}

        {/* Description */}
        {zone.description &&
          zone.description !== `Zone ${zoneId}` && (
            <p className="text-sm text-text-secondary leading-relaxed">
              {zone.description}
            </p>
          )}

        {/* Metrics grid */}
        <div className="grid grid-cols-2 gap-2">
          <MetricCard
            icon={Users}
            label="Total Visits"
            value={a.total_visits ?? 0}
            color={color}
          />
          <MetricCard
            icon={Users}
            label="Unique Visitors"
            value={a.unique_visitors ?? 0}
            color={color}
          />
          <MetricCard
            icon={Clock}
            label="Avg Dwell"
            value={formatDuration(a.avg_dwell_seconds || 0)}
            color={color}
          />
          <MetricCard
            icon={Clock}
            label="P95 Dwell"
            value={formatDuration(a.p95_dwell_seconds || 0)}
            color={color}
          />
          <MetricCard
            icon={TrendingUp}
            label="Peak Hour"
            value={
              a.peak_hour != null ? `${a.peak_hour}:00` : "\u2014"
            }
            color={color}
          />
          <MetricCard
            icon={TrendingUp}
            label="Density"
            value={`${(a.density_people_per_m2_hr || 0).toFixed(1)}/m\u00B2/hr`}
            color={color}
          />
        </div>

        {/* Temporal sparkline */}
        {occupancyData.length > 0 && (
          <Section title="Occupancy Over Time" icon={BarChart3}>
            <div className="bg-bg-primary rounded-lg p-3 border border-border">
              <svg
                viewBox={`0 0 ${occupancyData.length * 24} 50`}
                className="w-full"
                style={{ height: 50 }}
              >
                {/* Sparkline area */}
                <path
                  d={
                    `M 0 50 ` +
                    occupancyData
                      .map((v, i) => `L ${i * 24 + 12} ${50 - (v / maxOcc) * 45}`)
                      .join(" ") +
                    ` L ${(occupancyData.length - 1) * 24 + 12} 50 Z`
                  }
                  fill={color}
                  fillOpacity={0.15}
                />
                {/* Sparkline */}
                <polyline
                  points={occupancyData
                    .map(
                      (v, i) =>
                        `${i * 24 + 12},${50 - (v / maxOcc) * 45}`
                    )
                    .join(" ")}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* Dots */}
                {occupancyData.map((v, i) => (
                  <circle
                    key={i}
                    cx={i * 24 + 12}
                    cy={50 - (v / maxOcc) * 45}
                    r={3}
                    fill={color}
                  >
                    <title>
                      Bin {i}: {v} occupants
                    </title>
                  </circle>
                ))}
              </svg>
              <div className="flex justify-between text-[8px] text-text-secondary font-mono mt-1">
                <span>0:00</span>
                <span>
                  {Math.round(
                    (occupancyData.length * (temporal?.time_bin_seconds || 300)) / 60
                  )}
                  :00
                </span>
              </div>
            </div>
          </Section>
        )}

        {/* Physical dimensions */}
        {zone.depth_info &&
          Object.keys(zone.depth_info).length > 0 && (
            <Section title="Physical Dimensions" icon={MapPin}>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {zone.depth_info.width_estimate_m != null && (
                  <div className="bg-bg-primary rounded px-2 py-1.5 border border-border">
                    <span className="text-text-secondary text-[10px] block">
                      Width
                    </span>
                    <span className="text-text-primary">
                      {zone.depth_info.width_estimate_m.toFixed(1)}m
                    </span>
                  </div>
                )}
                {zone.depth_info.depth_estimate_m != null && (
                  <div className="bg-bg-primary rounded px-2 py-1.5 border border-border">
                    <span className="text-text-secondary text-[10px] block">
                      Depth
                    </span>
                    <span className="text-text-primary">
                      {zone.depth_info.depth_estimate_m.toFixed(1)}m
                    </span>
                  </div>
                )}
                {zone.area_m2 > 0 && (
                  <div className="bg-bg-primary rounded px-2 py-1.5 border border-border">
                    <span className="text-text-secondary text-[10px] block">
                      Area
                    </span>
                    <span className="text-text-primary">
                      {zone.area_m2.toFixed(1)}m&sup2;
                    </span>
                  </div>
                )}
                {zone.depth_info.avg_depth_m != null && (
                  <div className="bg-bg-primary rounded px-2 py-1.5 border border-border">
                    <span className="text-text-secondary text-[10px] block">
                      Distance
                    </span>
                    <span className="text-text-primary">
                      {zone.depth_info.avg_depth_m.toFixed(1)}m
                    </span>
                  </div>
                )}
              </div>
            </Section>
          )}

        {/* Objects */}
        {zone.objects?.length > 0 && (
          <Section title="Objects Detected" icon={Package}>
            <div className="flex flex-wrap gap-1.5">
              {zone.objects.map((obj, i) => (
                <span
                  key={i}
                  className="text-[11px] font-mono bg-bg-hover px-2 py-0.5 rounded border border-border"
                >
                  {obj.name || obj}
                  {obj.count > 1 && (
                    <span className="text-text-secondary">
                      {" "}
                      &times;{obj.count}
                    </span>
                  )}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Signage */}
        {zone.signage?.text_elements?.length > 0 && (
          <Section title="Signage" icon={Type}>
            <div className="space-y-1">
              {zone.signage.text_elements.map((t, i) => (
                <div
                  key={i}
                  className="text-xs font-mono bg-bg-hover px-2 py-1 rounded border border-border"
                >
                  &ldquo;{t.text || t}&rdquo;
                  {t.confidence && (
                    <span className="text-text-secondary ml-2">
                      ({(t.confidence * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Hourly distribution */}
        {a.hourly_visits &&
          Object.keys(a.hourly_visits).length > 0 && (
            <Section title="Hourly Distribution">
              <div className="bg-bg-primary rounded-lg p-3 border border-border">
                <div className="flex items-end gap-0.5 h-16">
                  {Array.from({ length: 24 }, (_, h) => {
                    const val = a.hourly_visits[String(h)] || 0;
                    const maxH = Math.max(
                      ...Object.values(a.hourly_visits),
                      1
                    );
                    const pct = (val / maxH) * 100;
                    return (
                      <div
                        key={h}
                        className="flex-1 rounded-t-sm transition-all"
                        style={{
                          height: `${Math.max(pct, 2)}%`,
                          backgroundColor:
                            val > 0 ? color : "#1e1e2e",
                          opacity: val > 0 ? 0.7 : 0.3,
                        }}
                        title={`${h}:00 \u2014 ${val} visits`}
                      />
                    );
                  })}
                </div>
                <div className="flex justify-between text-[8px] text-text-secondary font-mono mt-1">
                  <span>0h</span>
                  <span>6h</span>
                  <span>12h</span>
                  <span>18h</span>
                  <span>24h</span>
                </div>
              </div>
            </Section>
          )}

        {/* Contributing strategies */}
        {zone.contributing_strategies?.length > 0 && (
          <Section title="Detection Strategies" icon={Layers}>
            <div className="flex flex-wrap gap-1.5">
              {zone.contributing_strategies.map((strat, i) => {
                const stratColor =
                  STRATEGY_COLORS[strat] || "#6e6e82";
                return (
                  <span
                    key={i}
                    className="text-[11px] font-mono px-2.5 py-1 rounded-full border"
                    style={{
                      backgroundColor: `${stratColor}15`,
                      borderColor: `${stratColor}40`,
                      color: stratColor,
                    }}
                  >
                    {strat.replace(/_/g, " ")}
                  </span>
                );
              })}
            </div>
          </Section>
        )}

        {/* Meta footer */}
        <div className="text-[10px] text-text-secondary font-mono pt-3 border-t border-border space-y-1">
          <div className="flex justify-between">
            <span>Strategy Agreement</span>
            <span className="text-text-primary">
              {zone.strategy_agreement || 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span>VLM Confidence</span>
            <span className="text-text-primary">
              {((zone.vlm_confidence || 0) * 100).toFixed(0)}%
            </span>
          </div>
          {zone.depth_info?.source && (
            <div className="flex justify-between">
              <span>Depth Source</span>
              <span className="text-text-primary">
                {zone.depth_info.source.replace(/_/g, " ")}
              </span>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        {Icon && (
          <Icon className="w-3.5 h-3.5 text-text-secondary" />
        )}
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h4>
      </div>
      {children}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-bg-hover rounded-lg px-3 py-2 border border-border/50">
      <div className="flex items-center gap-1 mb-0.5">
        <Icon className="w-3 h-3 text-text-secondary" />
        <span className="text-[10px] text-text-secondary uppercase">
          {label}
        </span>
      </div>
      <p className="text-sm font-mono font-semibold tabular-nums">
        {value}
      </p>
    </div>
  );
}
