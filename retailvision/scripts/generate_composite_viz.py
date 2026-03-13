"""Generate improved composite visualizations from pipeline results."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import numpy as np

# Enable Cyrillic text support
import matplotlib.font_manager as fm
# Try to use a font that supports Cyrillic
for font_name in ['DejaVu Sans', 'Arial', 'Noto Sans', 'Liberation Sans']:
    try:
        fm.findfont(font_name)
        plt.rcParams['font.family'] = font_name
        break
    except Exception:
        continue

from tracker.database import TrackDatabase
import struct

# ── Dark Observatory Theme ──
BG_DARK = "#0a0a0f"
BG_PANEL = "#12121a"
BORDER = "#1e1e2e"
TEXT_PRIMARY = "#e8e8ec"
TEXT_SECONDARY = "#6e6e82"
ACCENT_CYAN = "#00d4ff"
ACCENT_GREEN = "#00ff88"
ACCENT_ORANGE = "#ff9500"
ACCENT_PINK = "#ff3366"
ACCENT_PURPLE = "#b366ff"
ACCENT_YELLOW = "#ffc233"

ZONE_COLORS = ["#00d4ff", "#ff9500", "#00ff88", "#b366ff", "#ffc233",
               "#ff3366", "#4ecdc4", "#f77f00", "#9b59b6", "#e74c3c"]


def load_data():
    db_path = "output/real/tracks.db"
    video_id = "55748ef61510"

    db = TrackDatabase(db_path)
    video = db.get_video(video_id)

    # Load detections with bytes fix
    dets = db.get_detections(video_id)
    import pandas as pd
    df = pd.DataFrame(dets)

    for col in df.columns:
        if df[col].dtype == object and len(df) > 0:
            sample = df[col].iloc[0]
            if isinstance(sample, bytes) and len(sample) == 4:
                df[col] = df[col].apply(lambda b: struct.unpack('f', b)[0] if isinstance(b, bytes) else b)
                df[col] = df[col].astype(np.float64)

    tracks = db.get_track_summaries(video_id)
    ref_frame = db.get_reference_frame(video_id)

    # Try latest pipeline run first, then fallback
    for rpath in ["output/pipeline_run7/report.json", "output/real/report.json"]:
        report_path = Path(rpath)
        if report_path.exists():
            break
    report = json.loads(report_path.read_text()) if report_path.exists() else {}

    db.close()
    return df, tracks, video, ref_frame, report


def generate_improved_heatmap(df, video, viz_dir):
    """High-resolution detection heatmap with finer binning."""
    W, H = video["width"], video["height"]

    xs = df["x_center"].values
    ys = df["y_center"].values

    # Use fine binning: 2px per bin
    n_bins_x = W // 2
    n_bins_y = H // 2

    heatmap, xedges, yedges = np.histogram2d(
        xs, ys, bins=[n_bins_x, n_bins_y], range=[[0, W], [0, H]]
    )
    heatmap = heatmap.T

    # Smooth with Gaussian for visual appeal
    from scipy.ndimage import gaussian_filter
    heatmap_smooth = gaussian_filter(heatmap, sigma=3)

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_DARK)
    ax.set_facecolor(BG_DARK)

    im = ax.imshow(heatmap_smooth, cmap="inferno", aspect="auto",
                   extent=[0, W, H, 0], interpolation="bilinear")
    ax.set_title("Detection Density Heatmap (Gaussian-smoothed)", color=TEXT_PRIMARY,
                fontsize=14, fontweight="bold", pad=12)
    ax.tick_params(colors=TEXT_SECONDARY)
    for spine in ax.spines.values():
        spine.set_color(BORDER)

    cb = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cb.set_label("Detection Count", color=TEXT_SECONDARY, fontsize=10)
    cb.ax.tick_params(colors=TEXT_SECONDARY)

    plt.tight_layout()
    plt.savefig(str(viz_dir / "detection_heatmap.png"), dpi=150, facecolor=BG_DARK)
    plt.close()
    print(f"  Saved improved heatmap")


def generate_heatmap_overlay(df, video, ref_frame, viz_dir):
    """Heatmap overlaid on the actual camera frame."""
    W, H = video["width"], video["height"]
    frame_idx, frame = ref_frame

    xs = df["x_center"].values
    ys = df["y_center"].values

    heatmap, _, _ = np.histogram2d(xs, ys, bins=[W // 4, H // 4], range=[[0, W], [0, H]])
    heatmap = heatmap.T

    from scipy.ndimage import gaussian_filter
    heatmap_smooth = gaussian_filter(heatmap, sigma=4)

    # Normalize to 0-255
    heatmap_norm = (heatmap_smooth / heatmap_smooth.max() * 255).astype(np.uint8)
    heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_INFERNO)
    heatmap_color = cv2.resize(heatmap_color, (W, H))

    # Blend with frame
    alpha = 0.5
    blended = cv2.addWeighted(frame, 1 - alpha, heatmap_color, alpha, 0)

    # Add text
    cv2.putText(blended, "Detection Heatmap Overlay", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(blended, f"{len(df):,} detections over 30 min", (10, 60),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imwrite(str(viz_dir / "heatmap_overlay.png"), blended)
    print(f"  Saved heatmap overlay")


def generate_zones_perspective_labeled(ref_frame, report, viz_dir):
    """Zones on camera view with clear labels and legend. Uses PIL for Unicode text."""
    from PIL import Image, ImageDraw, ImageFont

    if not report.get("zones"):
        return

    _, frame = ref_frame
    frame = frame.copy()
    zones = report["zones"]
    H, W = frame.shape[:2]

    # Draw zone polygons with OpenCV (fast)
    for i, (zid, zone) in enumerate(zones.items()):
        color_hex = ZONE_COLORS[i % len(ZONE_COLORS)]
        r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
        color_bgr = (b, g, r)

        polygon = zone.get("polygon_pixel", [])
        if not polygon or len(polygon) < 3:
            bbox = zone.get("bbox_pixel", [])
            if bbox and len(bbox) >= 4:
                polygon = [[bbox[0], bbox[1]], [bbox[2], bbox[1]],
                          [bbox[2], bbox[3]], [bbox[0], bbox[3]]]
            else:
                continue

        pts = np.array(polygon, dtype=np.int32)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color_bgr)
        frame = cv2.addWeighted(overlay, 0.35, frame, 0.65, 0)
        cv2.polylines(frame, [pts], True, color_bgr, 2)

    # Switch to PIL for Unicode text rendering
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(frame_rgb)
    draw = ImageDraw.Draw(pil_img)

    # Load font with Cyrillic support
    try:
        font_label = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
        font_sub = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 10)
        font_title = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 16)
    except Exception:
        font_label = ImageFont.load_default()
        font_sub = font_label
        font_title = font_label

    analytics = report.get("analytics", {})

    for i, (zid, zone) in enumerate(zones.items()):
        color_hex = ZONE_COLORS[i % len(ZONE_COLORS)]
        r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)

        polygon = zone.get("polygon_pixel", [])
        bbox = zone.get("bbox_pixel", [])
        if polygon and len(polygon) >= 3:
            pts = np.array(polygon)
            cx, cy = int(np.mean(pts[:, 0])), int(np.mean(pts[:, 1]))
        elif bbox and len(bbox) >= 4:
            cx, cy = int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)
        else:
            continue

        label = zone.get("business_name", zid)
        a = analytics.get(zid, {})
        visits = a.get("total_visits", 0)
        dwell = a.get("avg_dwell_seconds", 0)
        sublabel = f"V:{visits} D:{dwell:.0f}s"

        # Measure text
        lbox = draw.textbbox((0, 0), label, font=font_label)
        tw, th = lbox[2] - lbox[0], lbox[3] - lbox[1]

        # Draw label background
        pad = 4
        x1 = cx - tw // 2 - pad
        y1 = cy - th - pad - 2
        x2 = cx + tw // 2 + pad
        y2 = cy + pad + 14
        draw.rectangle([x1, y1, x2, y2], fill=(20, 20, 30, 200), outline=(r, g, b))
        draw.text((cx - tw // 2, cy - th - 2), label, fill=(255, 255, 255), font=font_label)
        draw.text((cx - tw // 2, cy + 4), sublabel, fill=(200, 200, 200), font=font_sub)

    # Title bar
    draw.rectangle([0, 0, W, 36], fill=(10, 10, 15))
    quality = report.get("meta", {}).get("validation_metrics", {}).get("overall_score", 0)
    title = f"Zone Discovery: {len(zones)} zones | indoor_food_court | Quality: {quality:.2f}"
    draw.text((10, 8), title, fill=(232, 232, 236), font=font_title)

    # Convert back to OpenCV and save
    frame_out = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(viz_dir / "zones_perspective_labeled.png"), frame_out)
    print(f"  Saved labeled perspective zones")


def generate_composite_summary(df, tracks, video, ref_frame, report, viz_dir):
    """Multi-panel composite summary image."""
    fig = plt.figure(figsize=(24, 16), facecolor=BG_DARK)

    gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.35, wspace=0.3,
                           left=0.04, right=0.96, top=0.92, bottom=0.04)

    # ── Title ──
    fig.suptitle("RetailVision — Agentic Zone Discovery Pipeline",
                color=TEXT_PRIMARY, fontsize=20, fontweight="bold", y=0.97)
    fig.text(0.5, 0.945, f"Indoor Food Court | 30 min CCTV | {len(df):,} detections | "
             f"{len(tracks):,} tracks | {len(report.get('zones', {}))} zones discovered",
             color=TEXT_SECONDARY, fontsize=11, ha="center")

    # ── Panel 1: Camera frame with zones (top-left, 2 cols) ──
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.set_facecolor(BG_PANEL)
    _, frame = ref_frame
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    ax1.imshow(frame_rgb)
    ax1.set_title("Camera View + Discovered Zones", color=TEXT_PRIMARY, fontsize=12, fontweight="bold")
    ax1.tick_params(colors=TEXT_SECONDARY, labelsize=7)

    # Draw zone polygons
    zones = report.get("zones", {})
    for i, (zid, zone) in enumerate(zones.items()):
        polygon = zone.get("polygon_pixel", [])
        if polygon and len(polygon) >= 3:
            poly = np.array(polygon)
            color = ZONE_COLORS[i % len(ZONE_COLORS)]
            ax1.fill(poly[:, 0], poly[:, 1], alpha=0.25, color=color)
            ax1.plot(np.append(poly[:, 0], poly[0, 0]),
                    np.append(poly[:, 1], poly[0, 1]), color=color, linewidth=2)
            cx, cy = np.mean(poly[:, 0]), np.mean(poly[:, 1])
            ax1.text(cx, cy, zone.get("business_name", zid),
                    color="white", fontsize=8, ha="center", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc=BG_PANEL, ec=color, alpha=0.85))

    # ── Panel 2: BEV Track Plot (top-right, 2 cols) ──
    ax2 = fig.add_subplot(gs[0, 2:])
    ax2.set_facecolor(BG_PANEL)

    # Compute BEV coordinates (simple scaling)
    median_h = df["bbox_h"].median()
    px_per_m = median_h / 1.7
    bev_res = 1.0 / px_per_m

    bev_x = df["x_center"].values * bev_res
    bev_y = df["y_center"].values * bev_res

    # Sample for visualization
    sample_idx = np.random.choice(len(df), min(100000, len(df)), replace=False)
    ax2.scatter(bev_x[sample_idx], bev_y[sample_idx], c=ACCENT_CYAN, s=0.1, alpha=0.15)

    # Draw zone polygons on BEV
    for i, (zid, zone) in enumerate(zones.items()):
        poly_bev = zone.get("polygon_bev", [])
        if poly_bev and len(poly_bev) >= 3:
            poly = np.array(poly_bev)
            color = ZONE_COLORS[i % len(ZONE_COLORS)]
            ax2.fill(poly[:, 0], poly[:, 1], alpha=0.3, color=color)
            ax2.plot(np.append(poly[:, 0], poly[0, 0]),
                    np.append(poly[:, 1], poly[0, 1]), color=color, linewidth=2)

    ax2.set_title("Bird's Eye View + Zones", color=TEXT_PRIMARY, fontsize=12, fontweight="bold")
    ax2.set_xlabel("X (meters)", color=TEXT_SECONDARY, fontsize=9)
    ax2.set_ylabel("Y (meters)", color=TEXT_SECONDARY, fontsize=9)
    ax2.set_aspect("equal")
    ax2.tick_params(colors=TEXT_SECONDARY, labelsize=7)
    for spine in ax2.spines.values():
        spine.set_color(BORDER)

    # ── Panel 3: Detection Heatmap (mid-left, 2 cols) ──
    ax3 = fig.add_subplot(gs[1, :2])
    ax3.set_facecolor(BG_DARK)

    W, H = video["width"], video["height"]
    heatmap, _, _ = np.histogram2d(
        df["x_center"].values, df["y_center"].values,
        bins=[W // 4, H // 4], range=[[0, W], [0, H]]
    )
    from scipy.ndimage import gaussian_filter
    heatmap_smooth = gaussian_filter(heatmap.T, sigma=3)

    ax3.imshow(heatmap_smooth, cmap="inferno", aspect="auto",
              extent=[0, W, H, 0], interpolation="bilinear")
    ax3.set_title("Detection Density Heatmap", color=TEXT_PRIMARY, fontsize=12, fontweight="bold")
    ax3.tick_params(colors=TEXT_SECONDARY, labelsize=7)

    # ── Panel 4: Zone Analytics Bar Chart (mid-right) ──
    ax4 = fig.add_subplot(gs[1, 2])
    ax4.set_facecolor(BG_PANEL)

    zone_analytics = report.get("analytics", {})
    if zone_analytics:
        names = [zones[zid].get("business_name", zid) for zid in zone_analytics]
        visits = [zone_analytics[zid].get("total_visits", 0) for zid in zone_analytics]
        colors = [ZONE_COLORS[i % len(ZONE_COLORS)] for i in range(len(names))]

        bars = ax4.barh(names, visits, color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)
        ax4.set_xlabel("Total Visits", color=TEXT_SECONDARY, fontsize=9)
        ax4.set_title("Zone Visits (30 min)", color=TEXT_PRIMARY, fontsize=12, fontweight="bold")

    ax4.tick_params(colors=TEXT_SECONDARY, labelsize=8)
    for spine in ax4.spines.values():
        spine.set_color(BORDER)

    # ── Panel 5: Validation Metrics (mid-right) ──
    ax5 = fig.add_subplot(gs[1, 3])
    ax5.set_facecolor(BG_PANEL)

    metrics = report.get("meta", {}).get("validation_metrics", {})
    if metrics:
        labels = ["Silhouette", "Coverage", "Count\nSanity", "Multi-\nStrategy"]
        vals = [metrics.get("silhouette", 0), metrics.get("coverage_pct", 0),
                metrics.get("count_sanity", 0), metrics.get("multi_strategy_pct", 0)]
        met_colors = [ACCENT_CYAN, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_PURPLE]

        bars = ax5.bar(labels, vals, color=met_colors, alpha=0.8, edgecolor="white", linewidth=0.5)
        ax5.axhline(y=metrics.get("overall_score", 0), color=ACCENT_PINK,
                   linestyle="--", linewidth=2, label=f"Overall: {metrics.get('overall_score', 0):.2f}")
        ax5.set_ylim(0, 1.1)
        ax5.legend(facecolor=BG_PANEL, edgecolor=BORDER, labelcolor=TEXT_PRIMARY, fontsize=8)
        ax5.set_title("Quality Validation", color=TEXT_PRIMARY, fontsize=12, fontweight="bold")

    ax5.tick_params(colors=TEXT_SECONDARY, labelsize=8)
    for spine in ax5.spines.values():
        spine.set_color(BORDER)

    # ── Panel 6: Track Duration Distribution (bottom-left) ──
    ax6 = fig.add_subplot(gs[2, 0])
    ax6.set_facecolor(BG_PANEL)
    durations = [t["duration_seconds"] for t in tracks]
    ax6.hist(durations, bins=50, color=ACCENT_CYAN, alpha=0.7, edgecolor=ACCENT_CYAN)
    ax6.set_title("Track Duration", color=TEXT_PRIMARY, fontsize=11, fontweight="bold")
    ax6.set_xlabel("Seconds", color=TEXT_SECONDARY, fontsize=9)
    ax6.set_ylabel("Count", color=TEXT_SECONDARY, fontsize=9)
    ax6.tick_params(colors=TEXT_SECONDARY, labelsize=7)
    for spine in ax6.spines.values():
        spine.set_color(BORDER)

    # ── Panel 7: Zone Dwell Time (bottom) ──
    ax7 = fig.add_subplot(gs[2, 1])
    ax7.set_facecolor(BG_PANEL)
    if zone_analytics:
        names = [zones[zid].get("business_name", zid) for zid in zone_analytics]
        dwells = [zone_analytics[zid].get("avg_dwell_seconds", 0) for zid in zone_analytics]
        colors = [ZONE_COLORS[i % len(ZONE_COLORS)] for i in range(len(names))]
        ax7.barh(names, dwells, color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)
        ax7.set_xlabel("Avg Dwell (s)", color=TEXT_SECONDARY, fontsize=9)
    ax7.set_title("Avg Dwell Time", color=TEXT_PRIMARY, fontsize=11, fontweight="bold")
    ax7.tick_params(colors=TEXT_SECONDARY, labelsize=8)
    for spine in ax7.spines.values():
        spine.set_color(BORDER)

    # ── Panel 8: Zone Transitions / Flow (bottom) ──
    ax8 = fig.add_subplot(gs[2, 2])
    ax8.set_facecolor(BG_PANEL)
    transitions = report.get("flow", {}).get("transitions", [])
    if transitions:
        flow_labels = [f"{t['from_zone'][-3:]}\n→{t['to_zone'][-3:]}" for t in transitions[:8]]
        flow_counts = [t["count"] for t in transitions[:8]]
        ax8.barh(flow_labels, flow_counts, color=ACCENT_YELLOW, alpha=0.8,
                edgecolor="white", linewidth=0.5)
        ax8.set_xlabel("Transition Count", color=TEXT_SECONDARY, fontsize=9)
    ax8.set_title("Zone Transitions", color=TEXT_PRIMARY, fontsize=11, fontweight="bold")
    ax8.tick_params(colors=TEXT_SECONDARY, labelsize=8)
    for spine in ax8.spines.values():
        spine.set_color(BORDER)

    # ── Panel 9: KPI Summary (bottom-right) ──
    ax9 = fig.add_subplot(gs[2, 3])
    ax9.set_facecolor(BG_PANEL)
    ax9.set_xlim(0, 1)
    ax9.set_ylim(0, 1)
    ax9.axis("off")

    kpis = [
        ("Zones Discovered", str(len(zones)), ACCENT_CYAN),
        ("Total Detections", f"{len(df):,}", ACCENT_GREEN),
        ("Total Tracks", f"{len(tracks):,}", ACCENT_ORANGE),
        ("Quality Score", f"{metrics.get('overall_score', 0):.2f}", ACCENT_PINK),
        ("Scene Coverage", f"{metrics.get('coverage_pct', 0):.0%}", ACCENT_PURPLE),
        ("Scene Type", "Food Court", ACCENT_YELLOW),
    ]

    for i, (label, value, color) in enumerate(kpis):
        y = 0.88 - i * 0.155
        ax9.text(0.05, y, label, color=TEXT_SECONDARY, fontsize=10, va="center")
        ax9.text(0.95, y, value, color=color, fontsize=14, fontweight="bold",
                va="center", ha="right")
        ax9.axhline(y=y - 0.07, xmin=0.02, xmax=0.98, color=BORDER, linewidth=0.5)

    ax9.set_title("Pipeline Summary", color=TEXT_PRIMARY, fontsize=11, fontweight="bold")

    plt.savefig(str(viz_dir / "composite_summary.png"), dpi=150, facecolor=BG_DARK)
    plt.close()
    print(f"  Saved composite summary (24x16 panel)")


def main():
    viz_dir = Path("output/pipeline_run7/viz")
    viz_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    df, tracks, video, ref_frame, report = load_data()
    print(f"  {len(df):,} detections, {len(tracks):,} tracks, {len(report.get('zones', {}))} zones")

    print("\nGenerating visualizations...")
    generate_improved_heatmap(df, video, viz_dir)
    generate_heatmap_overlay(df, video, ref_frame, viz_dir)
    generate_zones_perspective_labeled(ref_frame, report, viz_dir)
    generate_composite_summary(df, tracks, video, ref_frame, report, viz_dir)

    print(f"\nAll visualizations saved to {viz_dir.resolve()}")


if __name__ == "__main__":
    main()
