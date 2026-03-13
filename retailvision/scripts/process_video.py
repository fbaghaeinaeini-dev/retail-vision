"""Process a real video: tracking → pipeline → visualizations.

Usage:
    python -m scripts.process_video --video "E:/Agentic-path/2026-03-05_04-00-00_fixed.mp4" --minutes 30
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import click
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger

from tracker.config import TrackerConfig
from tracker.database import TrackDatabase
from tracker.detector import RetailTracker


@click.command()
@click.option("--video", required=True, type=click.Path(exists=True), help="Input video file")
@click.option("--minutes", default=30, type=float, help="Process first N minutes")
@click.option("--output", default="output/real", help="Output directory")
@click.option("--db", default=None, help="Database path (default: output/real/tracks.db)")
@click.option("--openrouter-key", envvar="OPENROUTER_API_KEY", default="", help="OpenRouter API key")
@click.option("--skip-tracking", is_flag=True, help="Skip tracking (use existing DB)")
@click.option("--skip-pipeline", is_flag=True, help="Skip pipeline (only run tracking)")
@click.option("--conf", default=0.30, type=float, help="Detection confidence")
@click.option("--imgsz", default=1280, type=int, help="YOLO input size")
def main(video, minutes, output, db, openrouter_key, skip_tracking, skip_pipeline, conf, imgsz):
    """Process a real CCTV video through the full RetailVision stack."""
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = db or str(output_dir / "tracks.db")

    video_id = hashlib.md5(Path(video).name.encode()).hexdigest()[:12]

    # Get video info
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    max_frames = int(minutes * 60 * fps)
    max_frames = min(max_frames, total_frames)

    click.echo(f"\nVideo: {video}")
    click.echo(f"  Resolution: {W}x{H} @ {fps:.1f}fps")
    click.echo(f"  Total: {total_frames} frames ({total_frames/fps/60:.1f}min)")
    click.echo(f"  Processing: {max_frames} frames ({minutes:.0f}min)")
    click.echo(f"  Video ID: {video_id}")
    click.echo(f"  Output: {output_dir.resolve()}\n")

    # ── Step 1: Tracking ──
    if not skip_tracking:
        click.echo("=" * 60)
        click.echo("  STEP 1: Person Detection & Tracking (YOLO + BoTSORT)")
        click.echo("=" * 60)

        tracker_config = TrackerConfig(
            db_path=Path(db_path),
            yolo_model="yolo11m.pt",
            detection_conf=conf,
            imgsz=imgsz,
            keyframe_interval=150,
        )

        t0 = time.time()
        tracker = RetailTracker(tracker_config)
        result = tracker.process_video(video, video_id, max_frames=max_frames)
        tracking_time = time.time() - t0

        click.echo(f"\n  Tracking complete in {tracking_time:.0f}s")
        click.echo(f"  Detections: {result['detection_count']}")
        click.echo(f"  Tracks: {result['track_count']}")
        click.echo(f"  Speed: {max_frames / tracking_time:.1f} fps\n")

        # Generate tracking visualizations
        _generate_tracking_viz(db_path, video_id, video, output_dir, max_frames, fps)
    else:
        click.echo("Skipping tracking (--skip-tracking)")

    # ── Step 2: Pipeline ──
    if not skip_pipeline:
        click.echo("\n" + "=" * 60)
        click.echo("  STEP 2: Zone Discovery Agent Pipeline (26 tools)")
        click.echo("=" * 60)

        from agent.config import PipelineConfig
        from agent.orchestrator import ZoneDiscoveryAgent

        pipeline_config = PipelineConfig(
            db_path=Path(db_path),
            video_id=video_id,
            output_dir=output_dir,
            openrouter_api_key=openrouter_key,
            replicate_api_token="",
            quality_threshold=0.30,
        )

        t0 = time.time()
        agent = ZoneDiscoveryAgent(pipeline_config)
        try:
            state = agent.run()
        except Exception as e:
            logger.error(f"Pipeline failed at '{agent.state.current_step}': {e}")
            _save_report(agent.get_report(), output_dir)
            click.echo(f"\n  Pipeline failed: {e}")
            click.echo(f"  Partial report saved.")
            sys.exit(1)

        pipeline_time = time.time() - t0
        report = agent.get_report()
        _save_report(report, output_dir)

        click.echo(f"\n  Pipeline complete in {pipeline_time:.0f}s")
        click.echo(f"  Zones discovered: {report['n_zones']}")
        click.echo(f"  Scene type: {report['scene_type']}")
        click.echo(f"  Calibration: {report['calibration_method']}")
        click.echo(f"  Quality: {'PASSED' if report['quality_passed'] else 'FAILED'}")

        # Generate pipeline visualizations
        _generate_pipeline_viz(state, output_dir)

        # Tool timing
        click.echo("\n  Tool Timing:")
        for entry in report["tool_history"]:
            status = "OK" if entry["success"] else "!!"
            click.echo(f"    [{status}] {entry['tool']:35s} {entry['duration']:6.1f}s")
    else:
        click.echo("Skipping pipeline (--skip-pipeline)")

    click.echo("\n" + "=" * 60)
    click.echo(f"  ALL DONE — Output: {output_dir.resolve()}")
    click.echo("=" * 60)


def _generate_tracking_viz(db_path, video_id, video_path, output_dir, max_frames, fps):
    """Generate tracking stage visualizations."""
    viz_dir = output_dir / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    db = TrackDatabase(db_path)

    # 1. Sample frame with detections overlay
    click.echo("  Generating tracking visualizations...")
    _viz_sample_frames(db, video_id, video_path, viz_dir, fps)

    # 2. Track statistics
    _viz_track_stats(db, video_id, viz_dir)

    # 3. Heatmap of detections
    _viz_detection_heatmap(db, video_id, viz_dir)

    db.close()
    click.echo(f"  Visualizations saved to {viz_dir}")


def _viz_sample_frames(db, video_id, video_path, viz_dir, fps):
    """Draw detection boxes on sample frames."""
    cap = cv2.VideoCapture(video_path)
    sample_times = [30, 120, 300, 600, 900]  # seconds

    for t_sec in sample_times:
        frame_idx = int(t_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            continue

        # Get detections for this frame range
        rows = db.conn.execute(
            "SELECT * FROM detections WHERE video_id = ? AND frame_idx BETWEEN ? AND ?",
            (video_id, frame_idx - 2, frame_idx + 2)
        ).fetchall()

        for r in rows:
            x1, y1, x2, y2 = int(r["bbox_x1"]), int(r["bbox_y1"]), int(r["bbox_x2"]), int(r["bbox_y2"])
            tid = r["track_id"]
            # Color by track_id
            color = _track_color(tid)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"#{tid}", (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        cv2.putText(frame, f"t={t_sec}s  ({len(rows)} detections)",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imwrite(str(viz_dir / f"frame_{t_sec:04d}s.png"), frame)

    cap.release()


def _viz_track_stats(db, video_id, viz_dir):
    """Plot track duration and detection count distributions."""
    tracks = db.get_track_summaries(video_id)
    if not tracks:
        return

    durations = [t["duration_seconds"] for t in tracks]
    counts = [t["num_detections"] for t in tracks]
    qualities = [t.get("quality_score", 0) or 0 for t in tracks]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4), facecolor="#0a0a0f")

    for ax in axes:
        ax.set_facecolor("#12121a")
        ax.tick_params(colors="#6e6e82")
        for spine in ax.spines.values():
            spine.set_color("#1e1e2e")

    axes[0].hist(durations, bins=50, color="#00d4ff", alpha=0.7, edgecolor="#00d4ff")
    axes[0].set_title("Track Duration (s)", color="#e8e8ec", fontsize=10)
    axes[0].set_xlabel("Seconds", color="#6e6e82")

    axes[1].hist(counts, bins=50, color="#ff9500", alpha=0.7, edgecolor="#ff9500")
    axes[1].set_title("Detections per Track", color="#e8e8ec", fontsize=10)
    axes[1].set_xlabel("Count", color="#6e6e82")

    axes[2].hist(qualities, bins=30, color="#00ff88", alpha=0.7, edgecolor="#00ff88")
    axes[2].set_title("Track Quality Score", color="#e8e8ec", fontsize=10)
    axes[2].set_xlabel("Score", color="#6e6e82")

    plt.tight_layout()
    plt.savefig(str(viz_dir / "track_stats.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()


def _viz_detection_heatmap(db, video_id, viz_dir):
    """2D detection position heatmap."""
    # Sample detections for speed
    rows = db.conn.execute(
        "SELECT x_center, y_center FROM detections WHERE video_id = ? ORDER BY RANDOM() LIMIT 200000",
        (video_id,)
    ).fetchall()

    if not rows:
        return

    video = db.get_video(video_id)
    W, H = video["width"], video["height"]

    xs = np.array([r["x_center"] for r in rows])
    ys = np.array([r["y_center"] for r in rows])

    heatmap, xedges, yedges = np.histogram2d(xs, ys, bins=[W // 8, H // 8],
                                              range=[[0, W], [0, H]])
    heatmap = heatmap.T

    fig, ax = plt.subplots(figsize=(12, 7), facecolor="#0a0a0f")
    ax.set_facecolor("#0a0a0f")
    im = ax.imshow(heatmap, cmap="inferno", aspect="auto", extent=[0, W, H, 0])
    ax.set_title("Detection Density Heatmap", color="#e8e8ec", fontsize=12)
    ax.tick_params(colors="#6e6e82")
    cb = plt.colorbar(im, ax=ax, shrink=0.8)
    cb.ax.yaxis.set_tick_params(color="#6e6e82")
    cb.ax.tick_params(colors="#6e6e82")
    plt.tight_layout()
    plt.savefig(str(viz_dir / "detection_heatmap.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()


def _generate_pipeline_viz(state, output_dir):
    """Generate rich pipeline-stage visualizations."""
    viz_dir = output_dir / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    # 1. Calibration plot (BEV tracks)
    if state.raw_tracks is not None and "bev_x_meters" in state.raw_tracks.columns:
        _viz_bev_tracks(state, viz_dir)

    # 2. Dwell points
    if state.dwell_points:
        _viz_dwell_points(state, viz_dir)

    # 3. Zone candidates per strategy
    _viz_strategy_candidates(state, viz_dir)

    # 4. Final zone registry summary
    if state.zone_registry:
        _viz_zone_summary(state, viz_dir)

    # 5. Validation metrics
    if state.validation_metrics:
        _viz_validation(state, viz_dir)

    click.echo(f"  Pipeline visualizations saved to {viz_dir}")


def _viz_bev_tracks(state, viz_dir):
    """Plot BEV trajectories."""
    df = state.raw_tracks
    fig, ax = plt.subplots(figsize=(10, 10), facecolor="#0a0a0f")
    ax.set_facecolor("#12121a")

    # Sample tracks
    track_ids = df["track_id"].unique()
    sample_ids = np.random.choice(track_ids, min(100, len(track_ids)), replace=False)

    for tid in sample_ids:
        t = df[df["track_id"] == tid]
        color = _track_color_mpl(int(tid))
        ax.plot(t["bev_x_meters"], t["bev_y_meters"], color=color, alpha=0.3, linewidth=0.5)

    ax.set_title("BEV Tracks (100 sample)", color="#e8e8ec", fontsize=12)
    ax.set_xlabel("X (meters)", color="#6e6e82")
    ax.set_ylabel("Y (meters)", color="#6e6e82")
    ax.tick_params(colors="#6e6e82")
    ax.set_aspect("equal")
    for spine in ax.spines.values():
        spine.set_color("#1e1e2e")
    plt.tight_layout()
    plt.savefig(str(viz_dir / "bev_tracks.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()


def _viz_dwell_points(state, viz_dir):
    """Plot dwell point locations with duration encoding."""
    fig, ax = plt.subplots(figsize=(10, 10), facecolor="#0a0a0f")
    ax.set_facecolor("#12121a")

    xs = [d.centroid_bev[0] for d in state.dwell_points]
    ys = [d.centroid_bev[1] for d in state.dwell_points]
    sizes = [min(d.duration_seconds * 0.5, 200) for d in state.dwell_points]

    sc = ax.scatter(xs, ys, s=sizes, c=[d.duration_seconds for d in state.dwell_points],
                    cmap="plasma", alpha=0.6, edgecolors="white", linewidths=0.3)
    cb = plt.colorbar(sc, ax=ax, shrink=0.8, label="Duration (s)")
    cb.ax.yaxis.set_tick_params(color="#6e6e82")
    cb.ax.tick_params(colors="#6e6e82")
    cb.set_label("Duration (s)", color="#6e6e82")

    ax.set_title(f"Dwell Points ({len(state.dwell_points)} events)", color="#e8e8ec", fontsize=12)
    ax.set_xlabel("BEV X (m)", color="#6e6e82")
    ax.set_ylabel("BEV Y (m)", color="#6e6e82")
    ax.tick_params(colors="#6e6e82")
    ax.set_aspect("equal")
    for spine in ax.spines.values():
        spine.set_color("#1e1e2e")
    plt.tight_layout()
    plt.savefig(str(viz_dir / "dwell_points.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()


def _viz_strategy_candidates(state, viz_dir):
    """Plot zone candidates from each strategy."""
    strategies = [
        ("Strategy A: Dwell Clustering", state.zone_candidates_A, "#00d4ff"),
        ("Strategy B: Occupancy Grid", state.zone_candidates_B, "#ff9500"),
        ("Strategy C: Trajectory Graph", state.zone_candidates_C, "#00ff88"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="#0a0a0f")
    for ax, (title, candidates, color) in zip(axes, strategies):
        ax.set_facecolor("#12121a")
        ax.set_title(f"{title} ({len(candidates)} zones)", color="#e8e8ec", fontsize=10)

        for c in candidates:
            poly = np.array(c.polygon_bev)
            if len(poly) >= 3:
                poly_closed = np.vstack([poly, poly[0]])
                ax.fill(poly_closed[:, 0], poly_closed[:, 1], alpha=0.2, color=color)
                ax.plot(poly_closed[:, 0], poly_closed[:, 1], color=color, linewidth=1)
                ax.text(c.centroid_bev[0], c.centroid_bev[1], c.zone_id,
                       color="white", fontsize=6, ha="center")

        ax.set_aspect("equal")
        ax.tick_params(colors="#6e6e82")
        for spine in ax.spines.values():
            spine.set_color("#1e1e2e")

    plt.tight_layout()
    plt.savefig(str(viz_dir / "strategy_candidates.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()


def _viz_zone_summary(state, viz_dir):
    """Final zone registry visualization."""
    ZONE_COLORS = {
        "restaurant": "#ff6b35", "fast_food": "#ff6b35", "cafe": "#ffc233",
        "seating_area": "#339dff", "corridor": "#4a4a5e", "entrance": "#00ff88",
        "exit": "#00ff88", "shop": "#b366ff", "kiosk": "#b366ff", "unknown": "#3a3a4e",
    }

    fig, axes = plt.subplots(1, 2, figsize=(16, 8), facecolor="#0a0a0f")

    # Left: BEV zone map
    ax = axes[0]
    ax.set_facecolor("#12121a")
    ax.set_title(f"Discovered Zones ({len(state.zone_registry)})", color="#e8e8ec", fontsize=12)

    for zid, zone in state.zone_registry.items():
        poly = zone.get("polygon_bev", [])
        color = ZONE_COLORS.get(zone.get("zone_type", ""), "#3a3a4e")
        if len(poly) >= 3:
            poly = np.array(poly)
            poly_closed = np.vstack([poly, poly[0]])
            ax.fill(poly_closed[:, 0], poly_closed[:, 1], alpha=0.3, color=color)
            ax.plot(poly_closed[:, 0], poly_closed[:, 1], color=color, linewidth=2)
        cx = zone.get("centroid_bev", [0, 0])
        name = zone.get("business_name", zid)
        ax.text(cx[0], cx[1], name, color="white", fontsize=7, ha="center",
               fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="#12121a", ec=color, alpha=0.8))

    ax.set_aspect("equal")
    ax.set_xlabel("BEV X (m)", color="#6e6e82")
    ax.set_ylabel("BEV Y (m)", color="#6e6e82")
    ax.tick_params(colors="#6e6e82")
    for spine in ax.spines.values():
        spine.set_color("#1e1e2e")

    # Right: Zone type breakdown
    ax2 = axes[1]
    ax2.set_facecolor("#12121a")
    types = [z.get("zone_type", "unknown") for z in state.zone_registry.values()]
    type_counts = {}
    for t in types:
        type_counts[t] = type_counts.get(t, 0) + 1

    labels = list(type_counts.keys())
    values = list(type_counts.values())
    colors = [ZONE_COLORS.get(t, "#3a3a4e") for t in labels]

    ax2.barh(labels, values, color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)
    ax2.set_title("Zone Types", color="#e8e8ec", fontsize=12)
    ax2.set_xlabel("Count", color="#6e6e82")
    ax2.tick_params(colors="#6e6e82")
    for spine in ax2.spines.values():
        spine.set_color("#1e1e2e")

    plt.tight_layout()
    plt.savefig(str(viz_dir / "zone_summary.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()

    # Also: camera perspective view with zones
    if state.reference_frame is not None:
        _viz_perspective_zones(state, viz_dir)


def _viz_perspective_zones(state, viz_dir):
    """Draw zones on camera reference frame."""
    ZONE_COLORS_BGR = {
        "restaurant": (53, 107, 255), "fast_food": (53, 107, 255), "cafe": (51, 194, 255),
        "seating_area": (255, 157, 51), "corridor": (94, 94, 74), "entrance": (136, 255, 0),
        "exit": (136, 255, 0), "shop": (179, 102, 255), "unknown": (78, 78, 58),
    }

    frame = state.reference_frame.copy()
    for zid, zone in state.zone_registry.items():
        polygon = zone.get("polygon_pixel", [])
        if not polygon or len(polygon) < 3:
            bbox = zone.get("bbox_pixel", [])
            if bbox and len(bbox) >= 4:
                polygon = [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]]
            else:
                continue

        pts = np.array(polygon, dtype=np.int32)
        color = ZONE_COLORS_BGR.get(zone.get("zone_type", ""), (78, 78, 58))

        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color)
        frame = cv2.addWeighted(overlay, 0.35, frame, 0.65, 0)
        cv2.polylines(frame, [pts], True, color, 2)

        cx = int(np.mean(pts[:, 0]))
        cy = int(np.mean(pts[:, 1]))
        label = zone.get("business_name", zid)
        cv2.putText(frame, label, (cx - 40, cy),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    cv2.imwrite(str(viz_dir / "zones_perspective.png"), frame)


def _viz_validation(state, viz_dir):
    """Radar/bar chart of validation metrics."""
    m = state.validation_metrics
    if not m:
        return

    metrics = {
        "Silhouette": max(0, m.get("silhouette", 0)),
        "Coverage": m.get("coverage_pct", 0),
        "VLM Agreement": m.get("vlm_agreement", 0),
        "Count Sanity": m.get("count_sanity", 0),
        "Multi-Strategy": m.get("multi_strategy_pct", 0),
    }

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#0a0a0f")
    ax.set_facecolor("#12121a")

    labels = list(metrics.keys())
    values = list(metrics.values())
    colors = ["#00d4ff", "#00ff88", "#ffc233", "#ff9500", "#b366ff"]

    bars = ax.barh(labels, values, color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, 1)
    ax.axvline(x=m.get("overall_score", 0), color="#ff3366", linestyle="--", linewidth=2, label=f"Overall: {m.get('overall_score', 0):.2f}")
    ax.legend(loc="lower right", facecolor="#12121a", edgecolor="#1e1e2e", labelcolor="#e8e8ec")

    ax.set_title("Validation Metrics", color="#e8e8ec", fontsize=12)
    ax.tick_params(colors="#6e6e82")
    for spine in ax.spines.values():
        spine.set_color("#1e1e2e")

    plt.tight_layout()
    plt.savefig(str(viz_dir / "validation.png"), dpi=150, facecolor="#0a0a0f")
    plt.close()


def _save_report(report, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "pipeline_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)


def _track_color(track_id):
    """Deterministic BGR color for a track ID."""
    np.random.seed(track_id * 7 + 13)
    return tuple(int(x) for x in np.random.randint(80, 255, 3))


def _track_color_mpl(track_id):
    """Deterministic matplotlib color string."""
    np.random.seed(track_id * 7 + 13)
    r, g, b = np.random.randint(80, 255, 3) / 255.0
    return (r, g, b)


if __name__ == "__main__":
    main()
