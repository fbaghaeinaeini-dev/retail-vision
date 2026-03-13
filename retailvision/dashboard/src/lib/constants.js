// dashboard/src/lib/constants.js

export const VIZ_TYPES = {
  zone_map:     { icon: '🗺️', label: 'Zone Map — Camera View' },
  zone_map_bev: { icon: '🏗️', label: 'Zone Map — Bird\'s Eye' },
  zone_detail:  { icon: '📍', label: 'Zone Detail' },
  bar_chart:    { icon: '📊', label: 'Bar Chart' },
  sankey:       { icon: '🔀', label: 'Flow Diagram' },
  temporal:     { icon: '⏱️', label: 'Temporal Pattern' },
  kpi_cards:    { icon: '📈', label: 'KPI Cards' },
  data_table:   { icon: '📋', label: 'Data Table' },
  heatmap_image:{ icon: '🔥', label: 'Heatmap' },
  video_player: { icon: '🎥', label: 'Video Player' },
};

/** All viz type keys as a Set (replaces old PANEL_VIZ_TYPES) */
export const ALL_VIZ_TYPES = new Set(Object.keys(VIZ_TYPES));

/** Category grouping with accent colors for thumbnail strip */
export const VIZ_CATEGORIES = {
  zone_map:      { tag: 'Media', color: '#00d4ff' },
  zone_map_bev:  { tag: 'Media', color: '#00d4ff' },
  zone_detail:   { tag: 'Media', color: '#00d4ff' },
  bar_chart:     { tag: 'Chart', color: '#ff9500' },
  sankey:        { tag: 'Chart', color: '#ff9500' },
  temporal:      { tag: 'Chart', color: '#ff9500' },
  kpi_cards:     { tag: 'Data',  color: '#00ff88' },
  data_table:    { tag: 'Data',  color: '#00ff88' },
  video_player:  { tag: 'Media', color: '#b366ff' },
  heatmap_image: { tag: 'Media', color: '#b366ff' },
};

/** Get category info for a viz type */
export function getVizCategory(type) {
  return VIZ_CATEGORIES[type] || { tag: 'Viz', color: '#6e6e82' };
}

/** Get display label for a viz type, with fallback */
export function getVizLabel(type) {
  return VIZ_TYPES[type]?.label || type.replace(/_/g, ' ');
}

/** Get icon for a viz type */
export function getVizIcon(type) {
  return VIZ_TYPES[type]?.icon || '📊';
}
