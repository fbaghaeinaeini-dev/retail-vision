// dashboard/src/components/gallery/MediaGallery.jsx
import { useState, useCallback, useRef, useEffect, useMemo, lazy, Suspense } from 'react';
import VizCard from '../chat/VizCard';
import { getVizCategory } from '../../lib/constants';

const ZoneMapCard = lazy(() => import('../viz-cards/ZoneMapCard'));
const VideoPlayerCard = lazy(() => import('../viz-cards/VideoPlayerCard'));

/** Viz types that live under the Camera tab — excluded from Results */
const CAMERA_TYPES = new Set(['zone_map', 'video_player']);

/** Display order for category groups in the Results tab */
const CATEGORY_ORDER = ['Data', 'Chart', 'Media'];

function VizSkeleton() {
  return (
    <div className="w-full h-48 rounded-xl bg-bg-card border border-border animate-pulse flex items-center justify-center">
      <span className="text-xs text-text-secondary">Loading...</span>
    </div>
  );
}

export default function MediaGallery({
  vizList,
  activeIndex,
  onNavigate,
  report,
  onZoneClick,
  emptyImageSrc,
}) {
  const containerRef = useRef(null);

  // ── Split vizList into camera types vs result types ────────
  const resultVizList = useMemo(
    () => vizList.filter(v => !CAMERA_TYPES.has(v.type)),
    [vizList],
  );

  // Latest LLM-generated zone_map viz (carries highlight_zones, zone_info, etc.)
  const latestZoneMapViz = useMemo(() => {
    for (let i = vizList.length - 1; i >= 0; i--) {
      if (vizList[i].type === 'zone_map') return vizList[i];
    }
    return null;
  }, [vizList]);

  // Count of highlighted zones on the latest zone_map
  const highlightCount = latestZoneMapViz?.data?.highlight_zones?.length || 0;

  const total = resultVizList.length;

  // ── Group result vizzes by category (Data, Chart, Media) ───
  const groupedVizzes = useMemo(() => {
    const groups = {};
    for (const viz of resultVizList) {
      const cat = getVizCategory(viz.type);
      const tag = cat.tag;
      if (!groups[tag]) groups[tag] = { tag, color: cat.color, items: [] };
      groups[tag].items.push(viz);
    }
    // Return in fixed order, skip empty groups
    return CATEGORY_ORDER
      .filter(tag => groups[tag])
      .map(tag => groups[tag]);
  }, [resultVizList]);

  // ── Tab state ──────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('camera');   // 'camera' | 'results'
  const [cameraMode, setCameraMode] = useState('image');  // 'image' | 'video'
  const userPickedTab = useRef(false);

  // Auto-switch tab based on the active viz type (driven by LLM primaryViz)
  useEffect(() => {
    const activeViz = vizList[activeIndex];
    if (!activeViz) return;

    if (activeViz.type === 'video_player') {
      setActiveTab('camera');
      setCameraMode('video');
      userPickedTab.current = false;
    } else if (activeViz.type === 'zone_map') {
      setActiveTab('camera');
      setCameraMode('image');
      userPickedTab.current = false;
    } else if (!userPickedTab.current) {
      setActiveTab('results');
    }
  }, [activeIndex, vizList]);

  // Auto-switch to Results when new result vizzes arrive
  const prevResultCount = useRef(0);
  useEffect(() => {
    if (resultVizList.length > prevResultCount.current && !userPickedTab.current) {
      setActiveTab('results');
    }
    prevResultCount.current = resultVizList.length;
  }, [resultVizList.length]);

  // Reset flag when chat is cleared
  useEffect(() => {
    if (vizList.length === 0) {
      userPickedTab.current = false;
      setActiveTab('camera');
      setCameraMode('image');
    }
  }, [vizList.length]);

  const handleTabClick = useCallback((key) => {
    userPickedTab.current = true;
    setActiveTab(key);
  }, []);

  return (
    <div
      ref={containerRef}
      className="flex-1 min-w-[400px] flex flex-col bg-bg-primary outline-none relative"
    >
      {/* ── Compact icon-only tab bar ────────────────────────── */}
      <div className="flex items-center gap-0.5 px-2 border-b border-border bg-bg-card shrink-0 overflow-visible">
        {/* Camera tab */}
        <button
          onClick={() => handleTabClick('camera')}
          className={`
            relative flex items-center justify-center gap-1 h-9 px-2
            transition-colors cursor-pointer rounded-md overflow-visible
            ${activeTab === 'camera'
              ? 'text-accent-cyan'
              : 'text-text-secondary hover:text-text-primary'}
          `}
          title="Camera View / Video"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          {highlightCount > 0 && activeTab === 'camera' && (
            <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold leading-none bg-accent-cyan/20 text-accent-cyan">
              {highlightCount}
            </span>
          )}
          {highlightCount > 0 && activeTab !== 'camera' && (
            <span className="absolute -top-1 -right-1 z-10 min-w-[16px] h-4 px-1 flex items-center justify-center rounded-full text-[9px] font-bold leading-none bg-accent-orange text-white shadow-lg shadow-accent-orange/30 animate-[notifyPulse_2s_ease-in-out_infinite]">
              {highlightCount}
            </span>
          )}
          {activeTab === 'camera' && (
            <div className="absolute bottom-0 left-1.5 right-1.5 h-0.5 bg-accent-cyan rounded-full" />
          )}
        </button>

        {/* Results tab */}
        <button
          onClick={() => handleTabClick('results')}
          className={`
            relative flex items-center justify-center gap-1 h-9 px-2
            transition-colors cursor-pointer rounded-md overflow-visible
            ${activeTab === 'results'
              ? 'text-accent-cyan'
              : 'text-text-secondary hover:text-text-primary'}
          `}
          title="AI-generated results"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          {total > 0 && activeTab === 'results' && (
            <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold leading-none bg-accent-cyan/20 text-accent-cyan">
              {total}
            </span>
          )}
          {total > 0 && activeTab !== 'results' && (
            <span className="absolute -top-1 -right-1 z-10 min-w-[16px] h-4 px-1 flex items-center justify-center rounded-full text-[9px] font-bold leading-none bg-accent-orange text-white shadow-lg shadow-accent-orange/30 animate-[notifyPulse_2s_ease-in-out_infinite]">
              {total}
            </span>
          )}
          {activeTab === 'results' && (
            <div className="absolute bottom-0 left-1.5 right-1.5 h-0.5 bg-accent-cyan rounded-full" />
          )}
        </button>

        {/* Camera mode toggle (only when Camera tab is active) */}
        {activeTab === 'camera' && (
          <div className="ml-auto flex items-center gap-0.5 bg-bg-primary rounded-md p-0.5 border border-border">
            <button
              onClick={() => setCameraMode('image')}
              className={`p-1 rounded text-[10px] transition-colors cursor-pointer ${
                cameraMode === 'image'
                  ? 'bg-bg-card text-accent-cyan shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
              title="Zone map overlay"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
              </svg>
            </button>
            <button
              onClick={() => setCameraMode('video')}
              className={`p-1 rounded text-[10px] transition-colors cursor-pointer ${
                cameraMode === 'video'
                  ? 'bg-bg-card text-accent-cyan shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
              title="Video player"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* ── Tab content ──────────────────────────────────────── */}
      <div className="flex-1 relative overflow-hidden">
        {/* Camera tab */}
        {activeTab === 'camera' && (
          <div className="absolute inset-0 p-4 overflow-auto">
            <Suspense fallback={<VizSkeleton />}>
              <div className="w-full h-full">
                {cameraMode === 'image' ? (
                  latestZoneMapViz ? (
                    /* LLM-generated zone_map — includes highlight_zones, zone_info */
                    <ZoneMapCard
                      config={{ ...latestZoneMapViz.data, interactive: true }}
                      report={report}
                      onZoneClick={onZoneClick}
                    />
                  ) : (
                    /* Plain reference frame — no zone overlay until LLM generates one */
                    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
                      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
                        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
                          Camera View
                        </h4>
                      </div>
                      <img
                        src={emptyImageSrc || '/data/reference_frame.png'}
                        alt="Camera reference frame"
                        className="w-full h-auto block"
                        draggable={false}
                      />
                    </div>
                  )
                ) : (
                  <VideoPlayerCard
                    config={{ title: 'Original Footage' }}
                    report={report}
                  />
                )}
              </div>
            </Suspense>
          </div>
        )}

        {/* Results tab — all vizzes stacked vertically by category */}
        {activeTab === 'results' && (
          total === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center opacity-60">
              {emptyImageSrc && (
                <img
                  src={emptyImageSrc}
                  alt="Store camera view"
                  className="max-w-[60%] max-h-[60%] object-contain rounded-lg border border-border mb-4"
                />
              )}
              <p className="text-text-secondary text-sm">
                Ask a question to generate visualizations
              </p>
            </div>
          ) : (
            <div className="absolute inset-0 overflow-y-auto p-4">
              <div className="flex flex-col gap-4 max-w-[1200px] mx-auto">
                {groupedVizzes.map((group) => (
                  <section key={group.tag}>
                    {/* Category header */}
                    <div className="flex items-center gap-2 mb-2">
                      <div
                        className="w-1 h-4 rounded-full shrink-0"
                        style={{ background: group.color }}
                      />
                      <span
                        className="text-[10px] font-semibold uppercase tracking-wider"
                        style={{ color: group.color }}
                      >
                        {group.tag}
                      </span>
                      <span className="text-[9px] text-text-secondary">
                        {group.items.length} {group.items.length === 1 ? 'item' : 'items'}
                      </span>
                      <div className="flex-1 h-px bg-border/50" />
                    </div>
                    {/* Viz cards in this category */}
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                      {group.items.map((viz) => (
                        <div key={viz.id} className="min-h-0">
                          <VizCard
                            viz={viz.data}
                            report={report}
                            onZoneClick={onZoneClick}
                          />
                        </div>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
