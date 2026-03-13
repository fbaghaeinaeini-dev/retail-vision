export default function VideoPlayerCard({ config, report, onZoneClick }) {
  const title = config?.title || "Original Footage";

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h4>
        <span className="text-[9px] text-text-secondary font-mono">
          {report?.meta?.video_id || "video"}
        </span>
      </div>
      <div className="p-2">
        <video
          src="/api/video"
          controls
          className="w-full rounded"
          style={{ maxHeight: "400px" }}
          preload="metadata"
        >
          Your browser does not support video playback.
        </video>
      </div>
    </div>
  );
}
