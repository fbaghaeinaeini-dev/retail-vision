import { lazy, Suspense } from "react";

const CARD_MAP = {
  zone_map: lazy(() => import("../viz-cards/ZoneMapCard")),
  zone_map_bev: lazy(() => import("../viz-cards/ZoneMapBEVCard")),
  zone_detail: lazy(() => import("../viz-cards/ZoneDetailCard")),
  bar_chart: lazy(() => import("../viz-cards/BarChartCard")),
  sankey: lazy(() => import("../viz-cards/SankeyCard")),
  temporal: lazy(() => import("../viz-cards/TemporalCard")),
  kpi_cards: lazy(() => import("../viz-cards/KPICard")),
  data_table: lazy(() => import("../viz-cards/DataTableCard")),
  heatmap_image: lazy(() => import("../viz-cards/HeatmapImageCard")),
  video_player: lazy(() => import("../viz-cards/VideoPlayerCard")),
};

/**
 * Loading skeleton shown while a viz card chunk is being fetched.
 */
function VizSkeleton() {
  return (
    <div className="w-full h-48 rounded-xl bg-bg-card border border-border animate-pulse flex items-center justify-center">
      <span className="text-xs text-text-secondary">Loading visualization...</span>
    </div>
  );
}

/**
 * Lazy-loading router that maps viz.type to the correct card component.
 * Shows a loading skeleton during code-split fetch.
 */
export default function VizCard({ viz, report, onZoneClick }) {
  const CardComponent = CARD_MAP[viz?.type];

  if (!CardComponent) return null;

  return (
    <Suspense fallback={<VizSkeleton />}>
      <div className="w-full overflow-hidden">
        <CardComponent config={viz} report={report} onZoneClick={onZoneClick} />
      </div>
    </Suspense>
  );
}
