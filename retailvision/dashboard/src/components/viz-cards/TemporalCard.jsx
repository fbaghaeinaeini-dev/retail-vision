import { useMemo } from "react";
import { getZoneColor } from "../../lib/colors";

export default function TemporalCard({ config, report, onZoneClick }) {
  const highlightZone = config?.highlight_zone || config?.filter_zone || null;
  const title = config?.title || "Temporal Heatmap";
  const matrix = report?.temporal?.occupancy_matrix || {};
  const binSeconds = report?.temporal?.time_bin_seconds || 300;

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

  const sortedZoneIds = useMemo(() => {
    return [...zoneIds].sort((a, b) => {
      const sumA = (matrix[a] || []).reduce((s, v) => s + v, 0);
      const sumB = (matrix[b] || []).reduce((s, v) => s + v, 0);
      return sumB - sumA;
    });
  }, [zoneIds, matrix]);

  if (!zoneIds.length) {
    return (
      <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
        <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
            {title}
          </h4>
        </div>
        <div className="p-3 text-center">
          <p className="text-text-secondary text-xs">No temporal data</p>
        </div>
      </div>
    );
  }

  const displayBins = Math.min(maxBins, 80);
  const cellW = Math.max(400 / displayBins, 6);
  const cellH = 16;
  const labelW = 80;
  const svgW = labelW + displayBins * cellW + 10;
  const svgH = sortedZoneIds.length * cellH + 20;

  function intensityColor(value) {
    if (!maxValue || !value) return "#0a0a0f";
    const t = Math.min(value / maxValue, 1);
    if (t < 0.5) {
      const s = t * 2;
      return `rgb(${Math.round(10)}, ${Math.round(10 + s * 100)}, ${Math.round(30 + s * 160)})`;
    }
    const s = (t - 0.5) * 2;
    return `rgb(${Math.round(10 + s * 40)}, ${Math.round(110 + s * 102)}, ${Math.round(190 + s * 65)})`;
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
    const z = report?.zones?.[zid];
    if (!z) return zid;
    return (z.business_name || zid).slice(0, 10);
  }

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h4>
        <span className="text-[9px] font-mono text-text-secondary">
          {Math.round(binSeconds / 60)}min bins
        </span>
      </div>
      <div className="p-2 overflow-x-auto" style={{ maxHeight: 180 }}>
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          className="w-full"
          style={{ minHeight: 100 }}
        >
          {/* Zone labels */}
          {sortedZoneIds.map((zid, row) => {
            const zoneType = report?.zones?.[zid]?.zone_type || "unknown";
            const color = getZoneColor(zoneType);
            const isHighlighted = zid === highlightZone;
            return (
              <g key={`lbl-${zid}`}>
                <rect
                  x={labelW - 8}
                  y={row * cellH + 2}
                  width={3}
                  height={cellH - 4}
                  rx={1}
                  fill={color}
                  fillOpacity={isHighlighted ? 1 : 0.6}
                />
                <text
                  x={labelW - 12}
                  y={row * cellH + cellH / 2}
                  fill={isHighlighted ? "#e8e8ec" : "#a8a8b8"}
                  fontSize={7}
                  fontFamily="DM Sans, sans-serif"
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontWeight={isHighlighted ? "600" : "400"}
                >
                  {getZoneShortName(zid)}
                </text>
              </g>
            );
          })}

          {/* Heatmap cells */}
          {sortedZoneIds.map((zid, row) => {
            const occ = matrix[zid] || [];
            const isHighlighted = zid === highlightZone;
            return occ.slice(0, displayBins).map((val, col) => (
              <rect
                key={`${row}-${col}`}
                x={labelW + col * cellW}
                y={row * cellH}
                width={cellW - 0.5}
                height={cellH - 1.5}
                fill={intensityColor(val)}
                stroke={isHighlighted ? "#00d4ff" : "transparent"}
                strokeWidth={isHighlighted ? 0.5 : 0}
                rx={1}
              >
                <title>
                  {getZoneShortName(zid)} @ {formatBinLabel(col)}: {val}
                </title>
              </rect>
            ));
          })}

          {/* Time axis */}
          {Array.from({ length: displayBins }, (_, i) => i)
            .filter((bin) => {
              if (displayBins <= 12) return true;
              if (displayBins <= 30) return bin % 3 === 0;
              return bin % 6 === 0;
            })
            .map((bin) => (
              <text
                key={`tl-${bin}`}
                x={labelW + bin * cellW + cellW / 2}
                y={sortedZoneIds.length * cellH + 10}
                fill="#6e6e82"
                fontSize={6}
                fontFamily="JetBrains Mono, monospace"
                textAnchor="middle"
              >
                {formatBinLabel(bin)}
              </text>
            ))}
        </svg>
      </div>
    </div>
  );
}
