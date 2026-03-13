import { useMemo, useState, useRef, useCallback } from "react";
import { getZoneColor } from "../../lib/colors";

const W = 1280;
const H = 720;
const MIN_ZOOM = 1;
const MAX_ZOOM = 5;

/**
 * Distinct color palette for individually-colored zones.
 * Each zone gets its own color based on index, regardless of type.
 */
const ZONE_PALETTE = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ef4444", // red
  "#06b6d4", // cyan
  "#f97316", // orange
  "#ec4899", // pink
  "#14b8a6", // teal
  "#a855f7", // purple
  "#eab308", // yellow
  "#6366f1", // indigo
  "#22c55e", // green
  "#e11d48", // rose
  "#0ea5e9", // sky
];

export default function ZoneMapCard({ config, report, onZoneClick }) {
  const highlightZones = config?.highlight_zones || [];
  const zoneInfo = config?.zone_info || {};
  const interactive = config?.interactive ?? !!onZoneClick;
  const title = config?.title || "Camera View";
  const zones = report?.zones || {};

  const [tooltip, setTooltip] = useState({ zoneId: null, x: 0, y: 0, visible: false });
  const [hoveredZone, setHoveredZone] = useState(null);

  // Zoom & pan state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });
  const panOrigin = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    setZoom((prev) => {
      const next = prev - e.deltaY * 0.002;
      return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
    });
  }, []);

  const handlePointerDown = useCallback((e) => {
    if (zoom <= 1) return;
    isPanning.current = true;
    panStart.current = { x: e.clientX, y: e.clientY };
    panOrigin.current = { ...pan };
    e.currentTarget.setPointerCapture(e.pointerId);
  }, [zoom, pan]);

  const handlePointerMove = useCallback((e) => {
    if (!isPanning.current) return;
    const dx = (e.clientX - panStart.current.x) / zoom;
    const dy = (e.clientY - panStart.current.y) / zoom;
    setPan({ x: panOrigin.current.x + dx, y: panOrigin.current.y + dy });
  }, [zoom]);

  const handlePointerUp = useCallback(() => {
    isPanning.current = false;
  }, []);

  const resetView = useCallback(() => {
    isPanning.current = false;
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const zoneList = useMemo(() => {
    return Object.entries(zones).map(([zid, z], index) => {
      const poly = z.polygon_pixel || [];
      const bbox = z.bbox_pixel || [];
      const cx =
        bbox.length >= 4
          ? (bbox[0] + bbox[2]) / 2
          : poly.length
            ? poly.reduce((s, p) => s + p[0], 0) / poly.length
            : 0;
      const cy =
        bbox.length >= 4
          ? (bbox[1] + bbox[3]) / 2
          : poly.length
            ? poly.reduce((s, p) => s + p[1], 0) / poly.length
            : 0;
      const bboxArea =
        bbox.length >= 4 ? (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) : 0;

      return {
        id: zid,
        name: z.business_name || zid,
        type: z.zone_type || "unknown",
        polygon: poly,
        cx,
        cy,
        bboxArea,
        color: ZONE_PALETTE[index % ZONE_PALETTE.length],
      };
    });
  }, [zones]);

  const sortedZones = useMemo(() => {
    return [...zoneList].sort((a, b) => b.bboxArea - a.bboxArea);
  }, [zoneList]);

  function toSvgPoints(polygon) {
    if (!polygon || polygon.length < 3) return "";
    return polygon.map(([x, y]) => `${x},${y}`).join(" ");
  }

  const highlightSet = new Set(highlightZones);
  const hasHighlights = highlightSet.size > 0;

  function handlePolygonClick(zoneId) {
    if (onZoneClick) {
      onZoneClick(zoneId);
    }
  }

  function handlePolygonMouseEnter(zoneId, e) {
    setHoveredZone(zoneId);
    const info = zoneInfo[zoneId];
    if (info) {
      const svgEl = e.target.closest("svg");
      if (svgEl) {
        const rect = svgEl.getBoundingClientRect();
        const clientX = (e.clientX - rect.left) / zoom;
        const clientY = (e.clientY - rect.top) / zoom;
        setTooltip({ zoneId, x: clientX, y: clientY, visible: true });
      }
    }
  }

  function handlePolygonMouseLeave() {
    setHoveredZone(null);
    setTooltip((prev) => ({ ...prev, visible: false }));
  }

  const tooltipInfo = tooltip.visible && tooltip.zoneId ? zoneInfo[tooltip.zoneId] : null;

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
      <div
        ref={containerRef}
        className="relative overflow-hidden"
        style={{ cursor: zoom > 1 ? "grab" : "default" }}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {/* Zoom controls */}
        <div className="absolute top-1.5 right-1.5 z-20 flex items-center gap-1">
          <button
            onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + 0.5))}
            className="w-5 h-5 rounded bg-bg-card/80 backdrop-blur border border-border text-text-secondary hover:text-text-primary text-[10px] flex items-center justify-center cursor-pointer"
            title="Zoom in"
          >+</button>
          <button
            onClick={() => setZoom((z) => { const next = Math.max(MIN_ZOOM, z - 0.5); if (next <= 1) setPan({ x: 0, y: 0 }); return next; })}
            className="w-5 h-5 rounded bg-bg-card/80 backdrop-blur border border-border text-text-secondary hover:text-text-primary text-[10px] flex items-center justify-center cursor-pointer"
            title="Zoom out"
          >−</button>
          <button
            onClick={resetView}
            className={`h-5 px-1.5 rounded backdrop-blur border text-[9px] flex items-center justify-center cursor-pointer transition-all ${
              zoom > 1
                ? "bg-accent-cyan/15 border-accent-cyan/40 text-accent-cyan hover:bg-accent-cyan/25"
                : "bg-bg-card/80 border-border text-text-secondary/40 pointer-events-none"
            }`}
            title="Reset zoom"
            disabled={zoom <= 1}
          >Reset</button>
        </div>

        <div
          style={{
            transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
            transformOrigin: "center center",
            transition: isPanning.current ? "none" : "transform 0.15s ease-out",
          }}
        >
          {/* Reference frame */}
          <img
            src="/data/reference_frame.png"
            alt="Camera reference frame"
            className="w-full h-auto block opacity-70"
            draggable={false}
          />

          {/* SVG overlay */}
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="absolute inset-0 w-full h-full"
            preserveAspectRatio="xMidYMid meet"
          >
          {/* Zone polygons */}
          {sortedZones.map((z) => {
            const isHighlighted = highlightSet.has(z.id);
            const isDimmed = hasHighlights && !isHighlighted;
            const isHovered = hoveredZone === z.id;
            const points = toSvgPoints(z.polygon);
            if (!points) return null;

            // Use zone's unique palette color
            const zoneColor = z.color;

            // Compute visual states
            let fillOpacity, strokeWidth, strokeOpacity;
            if (isHovered) {
              // Hover: brighten significantly
              fillOpacity = 0.55;
              strokeWidth = 3.5;
              strokeOpacity = 1;
            } else if (isHighlighted) {
              fillOpacity = 0.35;
              strokeWidth = 2.5;
              strokeOpacity = 0.9;
            } else if (isDimmed) {
              fillOpacity = 0.05;
              strokeWidth = 1;
              strokeOpacity = 0.2;
            } else {
              fillOpacity = 0.2;
              strokeWidth = 1.5;
              strokeOpacity = 0.6;
            }

            return (
              <g key={z.id}>
                <polygon
                  points={points}
                  fill={zoneColor}
                  fillOpacity={fillOpacity}
                  stroke={zoneColor}
                  strokeWidth={strokeWidth}
                  strokeOpacity={strokeOpacity}
                  strokeLinejoin="round"
                  style={{
                    cursor: interactive ? "pointer" : "default",
                    transition: "fill-opacity 0.15s, stroke-width 0.15s, stroke-opacity 0.15s",
                    filter: isHovered ? `drop-shadow(0 0 6px ${zoneColor})` : "none",
                  }}
                  onClick={() => handlePolygonClick(z.id)}
                  onMouseEnter={(e) => handlePolygonMouseEnter(z.id, e)}
                  onMouseLeave={handlePolygonMouseLeave}
                />
              </g>
            );
          })}

          {/* Labels at centroids */}
          {sortedZones.map((z) => {
            const isHighlighted = highlightSet.has(z.id);
            const isDimmed = hasHighlights && !isHighlighted;
            const isHovered = hoveredZone === z.id;
            const label = z.name.length > 14 ? z.name.slice(0, 12) + ".." : z.name;
            const lw = Math.max(label.length * 6.5 + 12, 40);
            const zoneColor = z.color;

            return (
              <g key={`lbl-${z.id}`} style={{ pointerEvents: "none" }}>
                <rect
                  x={z.cx - lw / 2}
                  y={z.cy - 9}
                  width={lw}
                  height={18}
                  rx={4}
                  fill="#0a0a0f"
                  fillOpacity={isDimmed ? 0.5 : isHovered ? 0.95 : 0.8}
                  stroke={zoneColor}
                  strokeWidth={isHovered ? 2 : isHighlighted ? 1.5 : 0.5}
                  strokeOpacity={isDimmed ? 0.3 : isHovered ? 1 : 0.7}
                  style={{ transition: "all 0.15s" }}
                />
                <text
                  x={z.cx}
                  y={z.cy + 1}
                  fill={isHovered ? "#fff" : isHighlighted ? "#fff" : isDimmed ? "#6e6e82" : "#c8c8d0"}
                  fontSize={isHovered ? "11" : "10"}
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight={isHovered ? "700" : "600"}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  style={{ transition: "all 0.15s" }}
                >
                  {label}
                </text>
              </g>
            );
          })}
        </svg>

          {/* Tooltip overlay */}
          {tooltipInfo && (
            <div
              className="absolute z-10 bg-bg-card border border-border rounded-lg p-2 shadow-xl pointer-events-none"
              style={{
                left: Math.min(tooltip.x + 8, (containerRef.current?.offsetWidth ?? 9999) - 230),
                top: Math.max(tooltip.y - 40, 4),
                maxWidth: 220,
              }}
            >
              <p className="text-xs font-semibold text-accent-orange mb-0.5">
                {tooltipInfo.name || tooltip.zoneId}
              </p>
              {tooltipInfo.description && (
                <p className="text-[10px] text-text-secondary leading-snug">
                  {tooltipInfo.description}
                </p>
              )}
            </div>
          )}
        </div>{/* end zoom wrapper */}
      </div>

      {/* Zone color legend */}
      {zoneList.length > 0 && (
        <div className="px-3 py-1.5 border-t border-border flex flex-wrap gap-x-3 gap-y-0.5">
          {zoneList.map((z) => (
            <span
              key={z.id}
              className="flex items-center gap-1 text-[9px] text-text-secondary cursor-pointer"
              style={{ opacity: isDimmedInLegend(z.id, hasHighlights, highlightSet, hoveredZone) ? 0.4 : 1 }}
              onMouseEnter={() => setHoveredZone(z.id)}
              onMouseLeave={() => setHoveredZone(null)}
              onClick={() => handlePolygonClick(z.id)}
            >
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: z.color }}
              />
              {z.name.length > 12 ? z.name.slice(0, 10) + ".." : z.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function isDimmedInLegend(zoneId, hasHighlights, highlightSet, hoveredZone) {
  if (hoveredZone) return hoveredZone !== zoneId;
  if (hasHighlights) return !highlightSet.has(zoneId);
  return false;
}
