import { useMemo, useState, useCallback } from "react";
import { getZoneColor, formatZoneTypeLabel } from "../lib/colors";

/**
 * Bird's Eye View zone map with density heatmap underlay,
 * labeled axes, smart label placement, and hover tooltips.
 */
export default function ZoneMapBEV({
  zones,
  spatial,
  analytics,
  selectedZone,
  onSelectZone,
}) {
  const bounds = spatial?.heatmap_bounds || {};
  const PADDING = 2;
  const xMin = (bounds.x_min || 0) - PADDING;
  const xMax = (bounds.x_max || 100) + PADDING;
  const yMin = (bounds.y_min || 0) - PADDING;
  const yMax = (bounds.y_max || 100) + PADDING;
  const W = xMax - xMin;
  const H = yMax - yMin;

  const [hoveredZone, setHoveredZone] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Margin for axes
  const MARGIN = { left: 5, bottom: 3, top: 1, right: 1 };
  const viewW = W + MARGIN.left + MARGIN.right;
  const viewH = H + MARGIN.top + MARGIN.bottom;

  const zoneList = useMemo(() => {
    return Object.entries(zones).map(([zid, z]) => ({
      id: zid,
      name: z.business_name || zid,
      type: z.zone_type || "unknown",
      polygon: z.polygon_bev || [],
      centroid: z.centroid_bev || [0, 0],
      area: z.area_m2 || 0,
      zoneNum: zid.replace("zone_", ""),
      shortLabel: (z.zone_type || "?").charAt(0).toUpperCase(),
    }));
  }, [zones]);

  // Sort: larger zones first (rendered behind), smaller on top
  const sortedZones = useMemo(() => {
    return [...zoneList].sort((a, b) => b.area - a.area);
  }, [zoneList]);

  // Density heatmap rendering from spatial.heatmap_density
  const densityCells = useMemo(() => {
    const density = spatial?.heatmap_density;
    const cellSize = spatial?.grid_cell_m || 0.5;
    if (!density || !Array.isArray(density) || density.length === 0) return null;

    let maxVal = 0;
    for (const row of density) {
      if (Array.isArray(row)) {
        for (const v of row) {
          if (v > maxVal) maxVal = v;
        }
      }
    }
    if (maxVal === 0) return null;

    const hb = spatial?.heatmap_bounds || {};
    const ox = hb.x_min || 0;
    const oy = hb.y_min || 0;

    const cells = [];
    for (let r = 0; r < density.length; r++) {
      const row = density[r];
      if (!Array.isArray(row)) continue;
      for (let c = 0; c < row.length; c++) {
        const val = row[c];
        if (val <= 0) continue;
        const t = val / maxVal;
        // Blue -> Cyan -> Yellow color ramp
        const red = t < 0.5 ? 0 : Math.round((t - 0.5) * 2 * 255);
        const green = t < 0.5 ? Math.round(t * 2 * 180) : 180 + Math.round((t - 0.5) * 2 * 75);
        const blue = t < 0.5 ? 120 + Math.round(t * 2 * 135) : Math.round((1 - t) * 2 * 255);
        cells.push({
          x: ox + c * cellSize - xMin + MARGIN.left,
          y: oy + r * cellSize - yMin + MARGIN.top,
          w: cellSize,
          h: cellSize,
          color: `rgb(${red},${green},${blue})`,
          opacity: 0.25 + t * 0.45,
        });
      }
    }
    return cells;
  }, [spatial, xMin, yMin]);

  function toSvgPoints(polygon) {
    if (!polygon || polygon.length < 3) return "";
    return polygon
      .map(([x, y]) => `${x - xMin + MARGIN.left},${y - yMin + MARGIN.top}`)
      .join(" ");
  }

  const handleMouseMove = useCallback((e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  }, []);

  const hoveredData = hoveredZone ? zones[hoveredZone] : null;
  const hoveredAnalyticsData = hoveredZone && analytics ? analytics[hoveredZone] : null;

  // Axis tick generation
  const xTicks = useMemo(() => {
    const step = W > 30 ? 10 : W > 15 ? 5 : 2;
    const ticks = [];
    const start = Math.ceil((xMin + PADDING) / step) * step;
    for (let v = start; v <= xMax - PADDING; v += step) {
      ticks.push(v);
    }
    return ticks;
  }, [xMin, xMax, W]);

  const yTicks = useMemo(() => {
    const step = H > 20 ? 5 : H > 10 ? 2 : 1;
    const ticks = [];
    const start = Math.ceil((yMin + PADDING) / step) * step;
    for (let v = start; v <= yMax - PADDING; v += step) {
      ticks.push(v);
    }
    return ticks;
  }, [yMin, yMax, H]);

  // Build legend
  const uniqueTypes = useMemo(() => {
    const types = new Set(zoneList.map((z) => z.type));
    return [...types].sort();
  }, [zoneList]);

  const AREA_THRESHOLD = 3; // m^2 - zones below this get numbered dots

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Bird&rsquo;s Eye View
        </h3>
        <span className="text-[10px] font-mono text-text-secondary">
          {W.toFixed(0)}m &times; {H.toFixed(0)}m
        </span>
      </div>

      <div
        className="relative bg-bg-primary p-2"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredZone(null)}
      >
        <svg
          viewBox={`0 0 ${viewW} ${viewH}`}
          className="w-full"
          style={{ aspectRatio: `${viewW} / ${viewH}`, maxHeight: 460 }}
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Grid lines */}
          {xTicks.map((v) => (
            <line
              key={`xg-${v}`}
              x1={v - xMin + MARGIN.left}
              y1={MARGIN.top}
              x2={v - xMin + MARGIN.left}
              y2={H + MARGIN.top}
              stroke="#1e1e2e"
              strokeWidth={0.15}
            />
          ))}
          {yTicks.map((v) => (
            <line
              key={`yg-${v}`}
              x1={MARGIN.left}
              y1={v - yMin + MARGIN.top}
              x2={W + MARGIN.left}
              y2={v - yMin + MARGIN.top}
              stroke="#1e1e2e"
              strokeWidth={0.15}
            />
          ))}

          {/* Axis labels */}
          {xTicks.map((v) => (
            <text
              key={`xl-${v}`}
              x={v - xMin + MARGIN.left}
              y={H + MARGIN.top + 2}
              fill="#6e6e82"
              fontSize={1.4}
              fontFamily="JetBrains Mono, monospace"
              textAnchor="middle"
            >
              {v.toFixed(0)}m
            </text>
          ))}
          {yTicks.map((v) => (
            <text
              key={`yl-${v}`}
              x={MARGIN.left - 0.5}
              y={v - yMin + MARGIN.top + 0.4}
              fill="#6e6e82"
              fontSize={1.4}
              fontFamily="JetBrains Mono, monospace"
              textAnchor="end"
              dominantBaseline="middle"
            >
              {v.toFixed(0)}m
            </text>
          ))}

          {/* Density heatmap underlay */}
          {densityCells &&
            densityCells.map((c, i) => (
              <rect
                key={`dc-${i}`}
                x={c.x}
                y={c.y}
                width={c.w}
                height={c.h}
                fill={c.color}
                opacity={c.opacity}
              />
            ))}

          {/* Zone polygons — reduced opacity to avoid visual clutter */}
          {sortedZones.map((z) => {
            const color = getZoneColor(z.type);
            const isSelected = z.id === selectedZone;
            const isHovered = z.id === hoveredZone;
            const points = toSvgPoints(z.polygon);

            if (!points) return null;

            return (
              <g
                key={z.id}
                onClick={() => onSelectZone(z.id)}
                onMouseEnter={() => setHoveredZone(z.id)}
                className="cursor-pointer"
              >
                <polygon
                  points={points}
                  fill={color}
                  fillOpacity={
                    isSelected ? 0.35 : isHovered ? 0.25 : 0.08
                  }
                  stroke={color}
                  strokeWidth={isSelected ? 0.4 : isHovered ? 0.3 : 0.15}
                  strokeOpacity={isSelected || isHovered ? 1 : 0.5}
                  strokeLinejoin="round"
                />
              </g>
            );
          })}

          {/* Labels layer — compact names to avoid overlap */}
          {sortedZones.map((z) => {
            const color = getZoneColor(z.type);
            const cx = z.centroid[0] - xMin + MARGIN.left;
            const cy = z.centroid[1] - yMin + MARGIN.top;
            const isSelected = z.id === selectedZone;
            const isHovered = z.id === hoveredZone;
            const rawLabel = z.name;
            const label = rawLabel.length > 10 ? rawLabel.slice(0, 9) + "\u2026" : rawLabel;
            const labelW = Math.max(label.length * 0.6 + 1, 3);

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
                  strokeWidth={isSelected || isHovered ? 0.15 : 0.06}
                  strokeOpacity={0.6}
                />
                <text
                  x={cx}
                  y={cy + 0.1}
                  fill={isSelected || isHovered ? "#fff" : "#c8c8d0"}
                  fontSize={0.8}
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight="600"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {/* Scale bar */}
          <g transform={`translate(${W + MARGIN.left - 8}, ${H + MARGIN.top - 1.5})`}>
            <line x1={0} y1={0} x2={5} y2={0} stroke="#e8e8ec" strokeWidth={0.2} />
            <line x1={0} y1={-0.4} x2={0} y2={0.4} stroke="#e8e8ec" strokeWidth={0.15} />
            <line x1={5} y1={-0.4} x2={5} y2={0.4} stroke="#e8e8ec" strokeWidth={0.15} />
            <text
              x={2.5}
              y={-0.8}
              fill="#e8e8ec"
              fontSize={1.2}
              textAnchor="middle"
              fontFamily="JetBrains Mono, monospace"
            >
              5m
            </text>
          </g>
        </svg>

        {/* Hover tooltip */}
        {hoveredZone && hoveredData && (
          <div
            className="absolute z-20 pointer-events-none"
            style={{
              left: Math.min(mousePos.x + 12, 260),
              top: Math.max(mousePos.y - 60, 4),
            }}
          >
            <div className="bg-bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-xl min-w-[170px]">
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{
                    backgroundColor: getZoneColor(hoveredData.zone_type),
                  }}
                />
                <span className="text-xs font-semibold text-text-primary truncate">
                  {hoveredData.business_name || hoveredZone}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] font-mono">
                <span className="text-text-secondary">Type</span>
                <span className="text-text-primary">
                  {formatZoneTypeLabel(hoveredData.zone_type)}
                </span>
                <span className="text-text-secondary">Area</span>
                <span className="text-text-primary">
                  {(hoveredData.area_m2 || 0).toFixed(1)}m&sup2;
                </span>
                {hoveredAnalyticsData && (
                  <>
                    <span className="text-text-secondary">Visits</span>
                    <span className="text-text-primary">
                      {hoveredAnalyticsData.total_visits || 0}
                    </span>
                    <span className="text-text-secondary">Density</span>
                    <span className="text-text-primary">
                      {(hoveredAnalyticsData.density_people_per_m2_hr || 0).toFixed(1)}/m&sup2;/hr
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="px-4 py-2 border-t border-border flex flex-wrap gap-3">
        {uniqueTypes.map((type) => (
          <div key={type} className="flex items-center gap-1.5">
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: getZoneColor(type) }}
            />
            <span className="text-[10px] text-text-secondary">
              {formatZoneTypeLabel(type)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
