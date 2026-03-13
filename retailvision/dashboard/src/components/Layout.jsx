import { Eye, Bug, Clock } from "lucide-react";

export default function Layout({
  meta,
  showDebug,
  onToggleDebug,
  navSections,
  onNavClick,
  children,
}) {
  return (
    <div className="min-h-screen bg-bg-primary font-sans">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-bg-card/80 backdrop-blur-md border-b border-border">
        <div className="max-w-[1920px] mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Eye className="w-5 h-5 text-accent-cyan" />
            <h1 className="text-sm font-semibold tracking-wide">
              RetailVision
            </h1>
            <span className="text-xs text-text-secondary font-mono hidden sm:inline">
              Zone Discovery
            </span>
          </div>

          {/* Section navigation */}
          {navSections && navSections.length > 0 && (
            <nav className="hidden md:flex items-center gap-1">
              {navSections.map((s) => (
                <button
                  key={s.id}
                  onClick={() => onNavClick?.(s.id)}
                  className="px-2.5 py-1 text-[11px] font-mono text-text-secondary hover:text-accent-cyan hover:bg-accent-cyan/5 rounded transition-colors"
                >
                  {s.label}
                </button>
              ))}
            </nav>
          )}

          <div className="flex items-center gap-3 text-xs text-text-secondary font-mono">
            {meta.video_id && (
              <span className="bg-bg-hover px-2 py-1 rounded hidden lg:inline-block">
                {meta.video_id}
              </span>
            )}
            {meta.scene_type && (
              <span className="bg-bg-hover px-2 py-1 rounded hidden lg:inline-block">
                {meta.scene_type.replace(/_/g, " ")}
              </span>
            )}
            {meta.duration_seconds > 0 && (
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {Math.round(meta.duration_seconds / 60)}m
              </span>
            )}
            {meta.quality_passed !== undefined && (
              <span
                className={`px-2 py-1 rounded ${
                  meta.quality_passed
                    ? "bg-accent-green/10 text-accent-green"
                    : "bg-accent-red/10 text-accent-red"
                }`}
              >
                {meta.quality_passed ? "QA PASS" : "QA FAIL"}
              </span>
            )}
            <button
              onClick={onToggleDebug}
              className={`p-1.5 rounded transition-colors ${
                showDebug
                  ? "bg-accent-amber/20 text-accent-amber"
                  : "hover:bg-bg-hover text-text-secondary"
              }`}
              title="Toggle debug inspector"
            >
              <Bug className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-[1920px] mx-auto px-4 py-4">
        {children}
      </main>
    </div>
  );
}
