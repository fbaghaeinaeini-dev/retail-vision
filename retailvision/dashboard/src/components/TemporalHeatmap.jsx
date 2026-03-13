import { useMemo, useState } from "react";
import { getZoneColor, formatZoneTypeLabel } from "../lib/colors";

/**
 * Temporal heatmap: zones (rows) x time bins (columns).
 * Includes a "Grid View" and a "Camera Overlay" tab for the
 * pipeline-generated heatmap overlay image.
 */
export default function TemporalHeatmap({ temporal, zones }) {
  const matrix = temporal?.occupancy_matrix || {};
  const binSeconds = temporal?.time_bin_seconds || 300;
  const rushPeriods = temporal?.rush_periods || {};
  const [activeTab, setActiveTab] = useState("grid");
  const [hoveredCell, setHoveredCell] = useState(null);

  const { zoneIds, maxBins, maxValue } = useMemo(() => {
    const zoneIds = Object.keys(matrix);
    let maxBins = 0;
    let maxValue = 0;
    for (const occ of Object.values(matrix)) {
      if (Array.isArray(occ)) {
        maxBins = Math.max(maxBins, occ.length);
        for (const v of occ) maxValue = Math.max(maxValue, v);
      }
    }
    return { zoneIds, maxBins, maxValue };
  }, [matrix]);

  // Sort zones by total occupancy (most active first)
  const sortedZoneIds = useMemo(() => {
    return [...zoneIds].sort((a, b) => {
      const sumA = (matrix[a] || []).reduce((s, v) => s + v, 0);
      const sumB = (matrix[b] || []).reduce((s, v) => s + v, 0);
      return sumB - sumA;
    });
  }, [zoneIds, matrix]);

  if (!zoneIds.length) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-6 text-center">
        <p className="text-text-secondary text-sm">No temporal data available</p>
      </div>
    );
  }

  const displayBins = Math.min(maxBins, 120);
  const cellW = Math.max(600 / displayBins, 8);
  const cellH = 22;
  const labelW = 130;
  const svgW = labelW + displayBins * cellW + 40;
  const svgH = sortedZoneIds.length * cellH + 35;

  function intensityColor(value) {
    if (!maxValue || !value) return "#0a0a0f";
    const t = Math.min(value / maxValue, 1);
    // Dark blue -> Cyan -> Warm white color ramp
    if (t < 0.25) {
      const s = t * 4;
      return `rgb(${Math.round(10)}, ${Math.round(10 + s * 60)}, ${Math.round(30 + s * 100)})`;
    }
    if (t < 0.5) {
      const s = (t - 0.25) * 4;
      return `rgb(${Math.round(10)}, ${Math.round(70 + s * 142)}, ${Math.round(130 + s * 125)})`;
    }
    if (t < 0.75) {
      const s = (t - 0.5) * 4;
      return `rgb(${Math.round(10 + s * 200)}, ${Math.round(212 + s * 30)}, ${Math.round(255 - s * 60)})`;
    }
    const s = (t - 0.75) * 4;
    return `rgb(${Math.round(210 + s * 45)}, ${Math.round(242 + s * 13)}, ${Math.round(195 + s * 60)})`;
  }

  function formatBinLabel(binIdx) {
    const totalSeconds = binIdx * binSeconds;
    const m = Math.floor(totalSeconds / 60);
    const s = Math.floor(totalSeconds % 60);
    if (m < 60) return `${m}:${String(s).padStart(2, "0")}`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}:${String(rm).padStart(2, "0")}`;
  }

  function getZoneShortName(zid) {
    const z = zones[zid];
    if (!z) return zid;
    const typeLabel = formatZoneTypeLabel(z.zone_type);
    const num = zid.replace("zone_", "");
    return `${typeLabel} ${num}`;
  }

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Temporal Heatmap
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-text-secondary">
            {Math.round(binSeconds / 60)}min bins
          </span>
          <div className="flex bg-bg-primary rounded-md overflow-hidden border border-border">
            <button
              onClick={() => setActiveTab("grid")}
              className={`px-2 py-0.5 text-[10px] font-mono transition-colors ${
                activeTab === "grid"
                  ? "bg-accent-cyan/20 text-accent-cyan"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Grid
            </button>
            <button
              onClick={() => setActiveTab("overlay")}
              className={`px-2 py-0.5 text-[10px] font-mono transition-colors ${
                activeTab === "overlay"
                  ? "bg-accent-cyan/20 text-accent-cyan"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Camera
            </button>
          </div>
        </div>
      </div>

      {activeTab === "grid" ? (
        <div className="p-2 overflow-x-auto relative">
          <svg
            viewBox={`0 0 ${svgW} ${svgH}`}
            className="w-full"
            style={{ minHeight: 140 }}
          >
            {/* Zone labels */}
            {sortedZoneIds.map((zid, row) => {
              const zoneType = zones[zid]?.zone_type || "unknown";
              const color = getZoneColor(zoneType);
              return (
                <g key={`lbl-${zid}`}>
                  {/* Color indicator */}
                  <rect
                    x={labelW - 10}
                    y={row * cellH + 3}
                    width={4}
                    height={cellH - 6}
                    rx={1}
                    fill={color}
                    fillOpacity={0.7}
                  />
                  <text
                    x={labelW - 14}
                    y={row * cellH + cellH / 2}
                    fill="#e8e8ec"
                    fontSize={8.5}
                    fontFamily="DM Sans, sans-serif"
                    textAnchor="end"
                    dominantBaseline="middle"
                  >
                    {getZoneShortName(zid)}
                  </text>
                </g>
              );
            })}

            {/* Heatmap cells */}
            {sortedZoneIds.map((zid, row) => {
              const occ = matrix[zid] || [];
              const rushSet = new Set(rushPeriods[zid] || []);
              return occ.slice(0, displayBins).map((val, col) => {
                const isRush = rushSet.has(col);
                const isCellHovered =
                  hoveredCell &&
                  hoveredCell.row === row &&
                  hoveredCell.col === col;

                return (
                  <rect
                    key={`${row}-${col}`}
                    x={labelW + col * cellW}
                    y={row * cellH}
                    width={cellW - 1}
                    height={cellH - 2}
                    fill={intensityColor(val)}
                    stroke={
                      isRush
                        ? "#ff3366"
                        : isCellHovered
                          ? "#00d4ff"
                          : "transparent"
                    }
                    strokeWidth={isRush ? 1 : isCellHovered ? 0.8 : 0}
                    rx={1.5}
                    onMouseEnter={() =>
                      setHoveredCell({ row, col, zid, val })
                    }
                    onMouseLeave={() => setHoveredCell(null)}
                    className="cursor-crosshair"
                  >
                    <title>
                      {getZoneShortName(zid)} @ {formatBinLabel(col)}:{" "}
                      {val} occupants{isRush ? " (RUSH)" : ""}
                    </title>
                  </rect>
                );
              });
            })}

            {/* Time axis labels */}
            {Array.from(
              { length: displayBins },
              (_, i) => i
            )
              .filter((bin) => {
                // Show every bin if few bins, every N if many
                if (displayBins <= 12) return true;
                if (displayBins <= 30) return bin % 3 === 0;
                return bin % 6 === 0;
              })
              .map((bin) => (
                <text
                  key={`tl-${bin}`}
                  x={labelW + bin * cellW + cellW / 2}
                  y={sortedZoneIds.length * cellH + 12}
                  fill="#6e6e82"
                  fontSize={7}
                  fontFamily="JetBrains Mono, monospace"
                  textAnchor="middle"
                >
                  {formatBinLabel(bin)}
                </text>
              ))}

            {/* Color scale legend */}
            <g
              transform={`translate(${labelW + displayBins * cellW + 8}, 0)`}
            >
              {Array.from({ length: 8 }, (_, i) => {
                const t = i / 7;
                const val = t * maxValue;
                return (
                  <rect
                    key={`cs-${i}`}
                    x={0}
                    y={i * 12}
                    width={10}
                    height={10}
                    rx={1}
                    fill={intensityColor(val)}
                  />
                );
              })}
              <text
                x={14}
                y={6}
                fill="#6e6e82"
                fontSize={6}
                fontFamily="JetBrains Mono, monospace"
              >
                {maxValue}
              </text>
              <text
                x={14}
                y={90}
                fill="#6e6e82"
                fontSize={6}
                fontFamily="JetBrains Mono, monospace"
              >
                0
              </text>
            </g>
          </svg>

          {/* Rush period indicator legend */}
          {Object.keys(rushPeriods).length > 0 && (
            <div className="mt-2 flex items-center gap-2 px-2">
              <span className="w-3 h-3 rounded-sm border-2 border-accent-red" />
              <span className="text-[10px] text-text-secondary">
                Rush period
              </span>
            </div>
          )}
        </div>
      ) : (
        /* Camera overlay tab */
        <div className="p-2">
          <div className="relative rounded-lg overflow-hidden bg-bg-primary">
            <img
              src="/data/viz/heatmap_overlay.png"
              alt="Heatmap overlaid on camera view"
              className="w-full h-auto rounded-lg"
              onError={(e) => {
                e.target.style.display = "none";
                const fallback = e.target.parentElement.querySelector(
                  ".fallback-msg"
                );
                if (fallback) fallback.style.display = "flex";
              }}
            />
            <div
              className="fallback-msg hidden items-center justify-center p-12 text-text-secondary text-sm"
            >
              Heatmap overlay image not available
            </div>
          </div>
          <p className="text-[10px] text-text-secondary font-mono mt-2 px-1">
            Pipeline-generated density heatmap overlaid on reference camera
            frame
          </p>
        </div>
      )}
    </div>
  );
}
