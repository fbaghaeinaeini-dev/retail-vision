import { useMemo } from "react";
import { getZoneColor } from "../../lib/colors";

export default function ZoneMapBEVCard({ config, report, onZoneClick }) {
  const highlightZones = config?.highlight_zones || [];
  const title = config?.title || "Bird's Eye View";
  const zones = report?.zones || {};
  const spatial = report?.spatial || {};

  const bounds = spatial?.heatmap_bounds || {};
  const PADDING = 2;
  const xMin = (bounds.x_min || 0) - PADDING;
  const xMax = (bounds.x_max || 100) + PADDING;
  const yMin = (bounds.y_min || 0) - PADDING;
  const yMax = (bounds.y_max || 100) + PADDING;
  const W = xMax - xMin;
  const H = yMax - yMin;

  const zoneList = useMemo(() => {
    return Object.entries(zones).map(([zid, z]) => ({
      id: zid,
      name: (z.business_name || zid).slice(0, 10),
      type: z.zone_type || "unknown",
      polygon: z.polygon_bev || [],
      centroid: z.centroid_bev || [0, 0],
      area: z.area_m2 || 0,
    }));
  }, [zones]);

  const sortedZones = useMemo(() => {
    return [...zoneList].sort((a, b) => b.area - a.area);
  }, [zoneList]);

  function toSvgPoints(polygon) {
    if (!polygon || polygon.length < 3) return "";
    return polygon
      .map(([x, y]) => `${x - xMin},${y - yMin}`)
      .join(" ");
  }

  const highlightSet = new Set(highlightZones);

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h4>
        <span className="text-[9px] font-mono text-text-secondary">
          {zoneList.length} zones
        </span>
      </div>
      <div className="p-2" style={{ height: 200 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
          style={{ background: "#0a0a12" }}
        >
          {/* Zone polygons */}
          {sortedZones.map((z) => {
            const color = getZoneColor(z.type);
            const isHighlighted = highlightSet.has(z.id);
            const points = toSvgPoints(z.polygon);
            if (!points) return null;

            return (
              <g key={z.id}>
                <polygon
                  points={points}
                  fill={color}
                  fillOpacity={isHighlighted ? 0.35 : 0.1}
                  stroke={color}
                  strokeWidth={isHighlighted ? 0.4 : 0.15}
                  strokeOpacity={isHighlighted ? 1 : 0.5}
                  strokeLinejoin="round"
                />
              </g>
            );
          })}

          {/* Labels */}
          {sortedZones.map((z) => {
            const color = getZoneColor(z.type);
            const cx = z.centroid[0] - xMin;
            const cy = z.centroid[1] - yMin;
            const isHighlighted = highlightSet.has(z.id);
            const labelW = Math.max(z.name.length * 0.6 + 1, 3);

            return (
              <g key={`lbl-${z.id}`} style={{ pointerEvents: "none" }}>
                <rect
                  x={cx - labelW / 2}
                  y={cy - 0.7}
                  width={labelW}
                  height={1.4}
                  rx={0.3}
                  fill="#0a0a0f"
                  fillOpacity={0.85}
                  stroke={color}
                  strokeWidth={isHighlighted ? 0.15 : 0.06}
                  strokeOpacity={0.6}
                />
                <text
                  x={cx}
                  y={cy + 0.1}
                  fill={isHighlighted ? "#fff" : "#c8c8d0"}
                  fontSize={0.8}
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight="600"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {z.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
