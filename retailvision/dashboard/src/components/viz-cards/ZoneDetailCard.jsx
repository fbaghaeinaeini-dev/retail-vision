import { useMemo } from "react";
import { getZoneColor, formatDuration, formatZoneTypeLabel } from "../../lib/colors";

/** Reference frame dimensions (matches the source image) */
const REF_W = 1280;
const REF_H = 720;

export default function ZoneDetailCard({ config, report }) {
  const zoneId = config?.zone_id;

  if (!zoneId || !report?.zones?.[zoneId]) {
    return (
      <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
        <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
            Zone Detail
          </h4>
        </div>
        <div className="p-3 text-center">
          <p className="text-text-secondary text-xs">Zone not found</p>
        </div>
      </div>
    );
  }

  const zone = report.zones[zoneId];
  const analytics = report.analytics?.[zoneId] || {};
  const color = getZoneColor(zone.zone_type);
  const duration = report.meta?.duration_seconds || 1;
  const visitsPerHr = duration > 0
    ? ((analytics.total_visits || 0) / (duration / 3600)).toFixed(1)
    : "0";

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          Zone Detail
        </h4>
        <span className="text-[9px] font-mono text-text-secondary">{zoneId}</span>
      </div>
      <div className="p-3">
        <div className="flex gap-3 mb-3">
          {/* Zone crop from reference frame using bbox_pixel */}
          <ZoneCrop zone={zone} refFrame={report?.config?.reference_frame} />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-accent-orange truncate">
              {zone.business_name || zoneId}
            </p>
            <p className="text-[10px] text-text-secondary">
              {formatZoneTypeLabel(zone.zone_type)}
            </p>
            <p className="text-[10px] text-text-secondary font-mono">
              {(zone.area_m2 || 0).toFixed(1)} m²
            </p>
          </div>
        </div>

        {/* Metric boxes: 2x2 grid */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-[#0a0a12] rounded px-2 py-1.5 border border-border/50">
            <p className="text-[8px] text-text-secondary uppercase tracking-wider font-semibold">
              Visits/hr
            </p>
            <p className="text-sm font-mono font-semibold text-accent-cyan tabular-nums">
              {visitsPerHr}
            </p>
          </div>
          <div className="bg-[#0a0a12] rounded px-2 py-1.5 border border-border/50">
            <p className="text-[8px] text-text-secondary uppercase tracking-wider font-semibold">
              Avg Dwell
            </p>
            <p className="text-sm font-mono font-semibold text-accent-cyan tabular-nums">
              {formatDuration(analytics.avg_dwell_seconds || 0)}
            </p>
          </div>
          <div className="bg-[#0a0a12] rounded px-2 py-1.5 border border-border/50">
            <p className="text-[8px] text-text-secondary uppercase tracking-wider font-semibold">
              Area
            </p>
            <p className="text-sm font-mono font-semibold text-accent-cyan tabular-nums">
              {(zone.area_m2 || 0).toFixed(1)}m²
            </p>
          </div>
          <div className="bg-[#0a0a12] rounded px-2 py-1.5 border border-border/50">
            <p className="text-[8px] text-text-secondary uppercase tracking-wider font-semibold">
              Density
            </p>
            <p className="text-sm font-mono font-semibold text-accent-cyan tabular-nums">
              {(analytics.density_people_per_m2_hr || 0).toFixed(1)}
            </p>
          </div>
        </div>

        {/* VLM-provided description */}
        {config?.description && (
          <p className="mt-3 text-xs text-text-secondary italic leading-relaxed">
            {config.description}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * Renders a cropped snapshot of a zone from the reference frame image.
 * Uses bbox_pixel [x1, y1, x2, y2] to clip the correct region.
 */
function ZoneCrop({ zone, refFrame }) {
  const bbox = zone?.bbox_pixel;
  const src = refFrame ? `/data/${refFrame}` : "/data/reference_frame.png";

  // Display box size
  const DISPLAY_W = 100;
  const DISPLAY_H = 75;

  const style = useMemo(() => {
    if (!bbox || bbox.length < 4) return null;

    const [x1, y1, x2, y2] = bbox;
    const cropW = x2 - x1;
    const cropH = y2 - y1;
    if (cropW <= 0 || cropH <= 0) return null;

    // Scale the full image so the crop region fills the display box
    const scaleX = DISPLAY_W / cropW;
    const scaleY = DISPLAY_H / cropH;
    const scale = Math.max(scaleX, scaleY);

    const imgW = REF_W * scale;
    const imgH = REF_H * scale;

    // Offset so the crop region is centered in the display box
    const offsetX = -(x1 * scale) + (DISPLAY_W - cropW * scale) / 2;
    const offsetY = -(y1 * scale) + (DISPLAY_H - cropH * scale) / 2;

    return {
      width: imgW,
      height: imgH,
      marginLeft: offsetX,
      marginTop: offsetY,
    };
  }, [bbox]);

  if (!style) {
    return (
      <div
        className="rounded bg-[#1e1e2e] border border-border flex items-center justify-center shrink-0"
        style={{ width: DISPLAY_W, height: DISPLAY_H }}
      >
        <span className="text-[8px] text-text-secondary font-mono">no bbox</span>
      </div>
    );
  }

  return (
    <div
      className="rounded border border-border shrink-0 overflow-hidden"
      style={{ width: DISPLAY_W, height: DISPLAY_H }}
    >
      <img
        src={src}
        alt="Zone crop"
        draggable={false}
        style={style}
        className="block max-w-none"
      />
    </div>
  );
}
