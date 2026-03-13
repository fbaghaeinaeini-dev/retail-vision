import { useState, lazy, Suspense, useRef, useCallback } from "react";
import { useReport } from "../hooks/useReport";
import Layout from "../components/Layout";
import KPIRibbon from "../components/KPIRibbon";
import ZoneMapPerspective from "../components/ZoneMapPerspective";
import ZoneMapBEV from "../components/ZoneMapBEV";
import SankeyFlow from "../components/SankeyFlow";
import TemporalHeatmap from "../components/TemporalHeatmap";
import ZoneDetailPanel from "../components/ZoneDetailPanel";
import ZoneBarChart from "../components/ZoneBarChart";
import ImageGallery from "../components/ImageGallery";
import DebugInspector from "../components/DebugInspector";
import PipelineFlow from "../components/PipelineFlow";
import PipelineLog from "../components/PipelineLog";

const Scene3D = lazy(() => import("../components/Scene3D"));

const NAV_SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "zones", label: "Zones" },
  { id: "flow", label: "Flow" },
  { id: "temporal", label: "Temporal" },
  { id: "gallery", label: "Gallery" },
  { id: "3d", label: "3D" },
  { id: "pipeline", label: "Pipeline" },
  { id: "log", label: "Log" },
];

export default function DashboardPage() {
  const { report, loading, error } = useReport();
  const [selectedZone, setSelectedZone] = useState(null);
  const [showDebug, setShowDebug] = useState(false);

  // Section refs for scroll navigation
  const sectionRefs = useRef({});
  const setSectionRef = useCallback((id) => (el) => {
    sectionRefs.current[id] = el;
  }, []);

  const scrollToSection = useCallback((id) => {
    const el = sectionRefs.current[id];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg-primary">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-text-secondary font-mono text-sm">
            Loading pipeline data...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg-primary">
        <div className="bg-bg-card border border-border rounded-xl p-8 max-w-md text-center">
          <p className="text-accent-red font-mono text-sm mb-2">
            Failed to load report
          </p>
          <p className="text-text-secondary text-sm">{error}</p>
          <p className="text-text-secondary text-xs mt-4">
            Place{" "}
            <code className="text-accent-cyan">report.json</code> in{" "}
            <code className="text-accent-cyan">
              dashboard/public/data/
            </code>
          </p>
        </div>
      </div>
    );
  }

  const zones = report.zones || {};
  const analytics = report.analytics || {};
  const flow = report.flow || {};
  const temporal = report.temporal || {};
  const spatial = report.spatial || {};
  const meta = report.meta || {};

  return (
    <Layout
      meta={meta}
      showDebug={showDebug}
      onToggleDebug={() => setShowDebug(!showDebug)}
      navSections={NAV_SECTIONS}
      onNavClick={scrollToSection}
    >
      {/* Section: Overview / KPIs */}
      <section ref={setSectionRef("overview")} id="section-overview">
        <KPIRibbon zones={zones} analytics={analytics} meta={meta} />
      </section>

      {/* Section: Zones */}
      <section
        ref={setSectionRef("zones")}
        id="section-zones"
        className="mt-6"
      >
        <SectionHeader
          title="Zone Maps"
          subtitle={`${Object.keys(zones).length} discovered zones`}
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
          <ZoneMapPerspective
            zones={zones}
            analytics={analytics}
            selectedZone={selectedZone}
            onSelectZone={setSelectedZone}
          />
          <ZoneMapBEV
            zones={zones}
            spatial={spatial}
            analytics={analytics}
            selectedZone={selectedZone}
            onSelectZone={setSelectedZone}
          />
        </div>
      </section>

      {/* Section: Flow */}
      <section
        ref={setSectionRef("flow")}
        id="section-flow"
        className="mt-6"
      >
        <SectionHeader
          title="Customer Flow"
          subtitle="Zone-to-zone transitions"
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
          <SankeyFlow flow={flow} zones={zones} />
          <ZoneBarChart analytics={analytics} zones={zones} />
        </div>
      </section>

      {/* Section: Temporal */}
      <section
        ref={setSectionRef("temporal")}
        id="section-temporal"
        className="mt-6"
      >
        <SectionHeader
          title="Temporal Analysis"
          subtitle="Occupancy patterns over time"
        />
        <div className="mt-3">
          <TemporalHeatmap temporal={temporal} zones={zones} />
        </div>
      </section>

      {/* Section: Gallery */}
      <section
        ref={setSectionRef("gallery")}
        id="section-gallery"
        className="mt-6"
      >
        <SectionHeader
          title="Pipeline Visualizations"
          subtitle="Generated analysis images"
        />
        <div className="mt-3">
          <ImageGallery />
        </div>
      </section>

      {/* Section: 3D */}
      <section
        ref={setSectionRef("3d")}
        id="section-3d"
        className="mt-6"
      >
        <SectionHeader
          title="3D Scene View"
          subtitle="Interactive zone layout"
        />
        <div className="mt-3">
          <Suspense
            fallback={
              <div className="bg-bg-card border border-border rounded-xl p-8 text-center">
                <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-text-secondary text-sm">
                  Loading 3D viewer...
                </p>
              </div>
            }
          >
            <Scene3D zones={zones} />
          </Suspense>
        </div>
      </section>

      {/* Section: Pipeline */}
      <section
        ref={setSectionRef("pipeline")}
        id="section-pipeline"
        className="mt-6 mb-8"
      >
        <SectionHeader
          title="Agent Pipeline"
          subtitle="30-tool execution flow"
        />
        <div className="mt-3">
          <PipelineFlow meta={meta} />
        </div>
      </section>

      {/* Section: Log */}
      <section
        ref={setSectionRef("log")}
        id="section-log"
        className="mt-6 mb-8"
      >
        <SectionHeader
          title="Execution Log"
          subtitle="Step-by-step tool execution with outputs"
        />
        <div className="mt-3">
          <PipelineLog meta={meta} />
        </div>
      </section>

      {/* Zone Detail Panel (slide-in) */}
      {selectedZone && (
        <ZoneDetailPanel
          zoneId={selectedZone}
          zone={zones[selectedZone]}
          analytics={analytics[selectedZone]}
          temporal={temporal}
          onClose={() => setSelectedZone(null)}
        />
      )}

      {/* Debug Inspector */}
      {showDebug && (
        <DebugInspector
          report={report}
          onClose={() => setShowDebug(false)}
        />
      )}
    </Layout>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="flex items-baseline gap-3">
      <h2 className="text-sm font-semibold text-text-primary tracking-wide">
        {title}
      </h2>
      {subtitle && (
        <span className="text-[11px] text-text-secondary font-mono">
          {subtitle}
        </span>
      )}
    </div>
  );
}
