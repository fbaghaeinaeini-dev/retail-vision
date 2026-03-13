/** Deterministic palette for any free-form zone type string. */
const PALETTE = [
  "#ff6b35", "#339dff", "#00ff88", "#b366ff", "#ffc233",
  "#ff9500", "#00d4ff", "#ff3366", "#88cc00", "#cc6699",
  "#4a9dff", "#ff8866", "#33ccaa", "#9966ff", "#ddaa33",
];

export function getZoneColor(zoneType) {
  if (!zoneType || zoneType === "unknown") return "#3a3a4e";
  let hash = 0;
  for (let i = 0; i < zoneType.length; i++) {
    hash = ((hash << 5) - hash + zoneType.charCodeAt(i)) | 0;
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

/** Format a zone_type slug into a human-readable label. */
export function formatZoneTypeLabel(zoneType) {
  if (!zoneType) return "Unknown";
  return zoneType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format seconds to human-readable duration. */
export function formatDuration(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

/** Format large numbers with K/M suffixes. */
export function formatNumber(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
