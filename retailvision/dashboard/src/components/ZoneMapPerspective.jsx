import { useMemo, useState, useCallback, useRef } from "react";
import { getZoneColor, formatZoneTypeLabel } from "../lib/colors";

const MIN_ZOOM = 1;
const MAX_ZOOM = 5;

/**
 * Zone polygons overlaid on the camera perspective view (reference_frame.png).
 * SVG viewBox matches the 1280x720 frame.
 * Supports pan & zoom via mouse wheel and drag.
 */
export default function ZoneMapPerspective({
  zones,
  analytics,
  selectedZone,
  onSelectZone,
}) {
  const W = 1280;
  const H = 720;

  const [hoveredZone, setHoveredZone] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Zoom/pan state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const containerRef = useRef(null);

  const zoneList = useMemo(() => {
    return Object.entries(zones).map(([zid, z]) => {
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
      const bboxW = bbox.length >= 4 ? bbox[2] - bbox[0] : 0;
      const bboxH = bbox.length >= 4 ? bbox[3] - bbox[1] : 0;
      const bboxArea = bboxW * bboxH;

      return {
        id: zid,
        name: z.business_name || zid,
        type: z.zone_type || "unknown",
        polygon: poly,
        bbox,
        cx,
        cy,
        bboxW,
        bboxH,
        bboxArea,
        area_m2: z.area_m2 || 0,
        shortLabel: (z.zone_type || "?").charAt(0).toUpperCase(),
        zoneNum: zid.replace("zone_", ""),
      };
    });
  }, [zones]);

  const sortedZones = useMemo(() => {
    return [...zoneList].sort((a, b) => b.bboxArea - a.bboxArea);
  }, [zoneList]);

  const labelData = useMemo(() => {
    const MIN_BBOX_FOR_LABEL = 4000;
    return zoneList.map((z) => ({
      ...z,
      showFullLabel: z.bboxArea > MIN_BBOX_FOR_LABEL,
    }));
  }, [zoneList]);

  const labelMap = useMemo(() => {
    const m = {};
    labelData.forEach((z) => {
      m[z.id] = z;
    });
    return m;
  }, [labelData]);

  function toSvgPoints(polygon) {
    if (!polygon || polygon.length < 3) return "";
    return polygon.map(([x, y]) => `${x},${y}`).join(" ");
  }

  const handleMouseMove = useCallback(
    (e) => {
      if (isPanning) {
        const dx = e.clientX - panStart.current.x;
        const dy = e.clientY - panStart.current.y;
        setPan({
          x: panStart.current.panX + dx,
          y: panStart.current.panY + dy,
        });
        return;
      }
      const rect = e.currentTarget.getBoundingClientRect();
      setMousePos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    },
    [isPanning]
  );

  const handleWheel = useCallback(
    (e) => {
      e.preventDefault();
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const delta = e.deltaY > 0 ? -0.15 : 0.15;
      const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom + delta));

      if (newZoom !== zoom) {
        // Zoom toward mouse position
        const scale = newZoom / zoom;
        setPan((prev) => ({
          x: mouseX - scale * (mouseX - prev.x),
          y: mouseY - scale * (mouseY - prev.y),
        }));
        setZoom(newZoom);
      }
    },
    [zoom]
  );

  const handleMouseDown = useCallback(
    (e) => {
      if (zoom <= 1) return;
      if (e.button !== 0) return;
      setIsPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
    },
    [zoom, pan]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const resetZoom = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const hoveredData = hoveredZone ? zones[hoveredZone] : null;
  const hoveredAnalytics =
    hoveredZone && analytics ? analytics[hoveredZone] : null;

  const uniqueTypes = useMemo(() => {
    const types = new Set(zoneList.map((z) => z.type));
    return [...types].sort();
  }, [zoneList]);

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Camera View
        </h3>
        <div className="flex items-center gap-2">
          {zoom > 1 && (
            <button
              onClick={resetZoom}
              className="text-[10px] font-mono text-accent-cyan hover:text-white transition-colors px-1.5 py-0.5 rounded border border-border hover:border-accent-cyan"
            >
              Reset {zoom.toFixed(1)}x
            </button>
          )}
          <span className="text-[10px] font-mono text-text-secondary">
            {zoneList.length} zones &middot; {W}&times;{H}
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        className="relative bg-bg-primary overflow-hidden"
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          setHoveredZone(null);
          setIsPanning(false);
        }}
        onWheel={handleWheel}
        style={{ cursor: isPanning ? "grabbing" : zoom > 1 ? "grab" : "default" }}
      >
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "0 0",
            transition: isPanning ? "none" : "transform 0.15s ease-out",
          }}
        >
          {/* Reference frame background */}
          <img
            src="/data/reference_frame.png"
            alt="Camera reference frame"
            className="w-full h-auto block opacity-70"
            draggable={false}
          />

          {/* SVG overlay matching 1280x720 */}
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="absolute inset-0 w-full h-full"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <filter id="labelShadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#000" floodOpacity="0.7" />
              </filter>
            </defs>

            {/* Zone polygons, sorted large-to-small for correct layering */}
            {sortedZones.map((z) => {
              const color = getZoneColor(z.type);
              const isSelected = z.id === selectedZone;
              const isHovered = z.id === hoveredZone;
              const points = toSvgPoints(z.polygon);

              if (!points) return null;

              return (
                <g
                  key={z.id}
                  onClick={(e) => {
                    if (!isPanning) onSelectZone(z.id);
                  }}
                  onMouseEnter={() => {
                    if (!isPanning) setHoveredZone(z.id);
                  }}
                  className="cursor-pointer"
                >
                  <polygon
                    points={points}
                    fill={color}
                    fillOpacity={
                      isSelected ? 0.45 : isHovered ? 0.35 : 0.15
                    }
                    stroke={color}
                    strokeWidth={isSelected ? 3 : isHovered ? 2.5 : 1.5}
                    strokeOpacity={isSelected || isHovered ? 1 : 0.7}
                    strokeLinejoin="round"
                  />
                </g>
              );
            })}

            {/* Labels layer on top — show full business names */}
            {sortedZones.map((z) => {
              const ld = labelMap[z.id];
              if (!ld) return null;
              const color = getZoneColor(z.type);
              const isSelected = z.id === selectedZone;
              const isHovered = z.id === hoveredZone;
              const label = z.name;
              const labelW = Math.max(label.length * 6.5 + 12, 40);

              return (
                <g key={`label-${z.id}`} filter="url(#labelShadow)" style={{ pointerEvents: "none" }}>
                  <rect
                    x={z.cx - labelW / 2}
                    y={z.cy - 10}
                    width={labelW}
                    height={20}
                    rx={4}
                    fill="#0a0a0f"
                    fillOpacity={0.8}
                    stroke={color}
                    strokeWidth={isSelected || isHovered ? 1.5 : 0.5}
                    strokeOpacity={0.7}
                  />
                  <text
                    x={z.cx}
                    y={z.cy + 1}
                    fill={isSelected || isHovered ? "#fff" : "#c8c8d0"}
                    fontSize="10"
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
          </svg>
        </div>

        {/* Zoom indicator */}
        {zoom > 1 && (
          <div className="absolute bottom-2 right-2 bg-bg-card/90 backdrop-blur-sm border border-border rounded px-2 py-1 text-[10px] font-mono text-text-secondary">
            {zoom.toFixed(1)}x &middot; scroll to zoom, drag to pan
          </div>
        )}

        {/* Hover tooltip */}
        {hoveredZone && hoveredData && !isPanning && (
          <div
            className="absolute z-20 pointer-events-none"
            style={{
              left: Math.min(mousePos.x + 12, 280),
              top: mousePos.y - 10,
            }}
          >
            <div className="bg-bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-2 shadow-xl min-w-[180px]">
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: getZoneColor(hoveredData.zone_type) }}
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
                <span className="text-text-primary">{(hoveredData.area_m2 || 0).toFixed(1)}m&sup2;</span>
                {hoveredAnalytics && (
                  <>
                    <span className="text-text-secondary">Visits</span>
                    <span className="text-text-primary">{hoveredAnalytics.total_visits || 0}</span>
                    <span className="text-text-secondary">Avg Dwell</span>
                    <span className="text-text-primary">
                      {(hoveredAnalytics.avg_dwell_seconds || 0).toFixed(1)}s
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
