"""Phase 1 Tool t03: Camera calibration from person-height regression.

THE primary calibration method — uses ONLY tracking data, NO API calls.

Math:
  In a pinhole camera, apparent height (pixels) of a standing person
  decreases with distance. Since all people are ~1.7m tall, measuring
  bbox heights at different y-positions reveals the ground plane geometry.

  Model: pixel_height = K / (y - y_vanishing)
  where K = focal_length * real_height, y_vp = vanishing point y

  This gives us a homography from image plane to ground plane (BEV).
"""

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger
from scipy.optimize import least_squares

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry

AVERAGE_PERSON_HEIGHT_M = 1.7


def _fallback_simple_scaling(state, config) -> ToolResult:
    """Fallback when insufficient data for perspective model.

    Uses a simple pixels-per-meter estimate from median bbox height.

    Coordinate system (consistent with perspective calibration):
      pixel → (homography) → bev_pixel → (* bev_scale) → meters
    So: meters = pixel * factor * bev_scale  where factor = 1/(px_per_meter * bev_scale)
    And: pixel = meters / bev_scale * (1/factor) = meters * px_per_meter
    """
    df = state.raw_tracks
    H_img, W_img = state.frame_shape[:2]
    median_h = df["bbox_h"].median()
    px_per_meter = median_h / AVERAGE_PERSON_HEIGHT_M

    # Homography: pixel → BEV pixel, where BEV_pixel * bev_scale = real meters
    bev_scale = config.bev_resolution  # 0.05 m/px target
    factor = 1.0 / (px_per_meter * bev_scale)
    homography = np.array([
        [factor, 0, 0],
        [0, factor, 0],
        [0, 0, 1],
    ])

    bev_w = int(W_img * factor) + 1
    bev_h = int(H_img * factor) + 1
    bev_w = min(max(bev_w, 200), 2500)
    bev_h = min(max(bev_h, 200), 2500)

    state.homography_matrix = homography
    state.bev_scale = bev_scale
    state.bev_size = (bev_w, bev_h)
    state.calibration_method = "simple_scaling"

    # Transform tracks via homography (same pattern as perspective calibration)
    pts = df[["x_center", "y_center"]].values.astype(np.float32)
    pts_h = np.hstack([pts, np.ones((len(pts), 1))])
    bev = (homography @ pts_h.T).T
    bev = bev[:, :2] / bev[:, 2:3]

    df["bev_x"] = bev[:, 0]
    df["bev_y"] = bev[:, 1]
    df["bev_x_meters"] = bev[:, 0] * bev_scale
    df["bev_y_meters"] = bev[:, 1] * bev_scale

    df["bev_dx"] = df.groupby("track_id")["bev_x_meters"].diff().fillna(0)
    df["bev_dy"] = df.groupby("track_id")["bev_y_meters"].diff().fillna(0)
    df["speed_m_s"] = np.sqrt(df["bev_dx"] ** 2 + df["bev_dy"] ** 2) / df["dt"].clip(lower=1e-6)

    logger.warning("Using fallback simple scaling calibration")
    return ToolResult(
        success=True,
        data={"method": "simple_scaling", "px_per_meter": float(px_per_meter)},
        message=f"Fallback calibration: {px_per_meter:.1f} px/m",
    )


def _plot_height_regression(y_positions, px_heights, K_fit, y_vp_fit):
    """Create debug plot of height regression."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    ax.scatter(y_positions, px_heights, c="cyan", s=20, label="Data (median per band)")
    y_smooth = np.linspace(y_positions.min(), y_positions.max(), 100)
    pred = K_fit / (y_smooth - y_vp_fit + 1e-6)
    ax.plot(y_smooth, pred, "r-", linewidth=2, label="Fit: K/(y - y_vp)")
    ax.set_xlabel("Y position (pixels)")
    ax.set_ylabel("BBox height (pixels)")
    ax.set_title(f"Person-Height Regression (K={K_fit:.0f}, y_vp={y_vp_fit:.0f})")
    ax.legend()
    ax.set_facecolor("#0a0a0f")
    fig.patch.set_facecolor("#0a0a0f")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")

    fig.tight_layout()
    fig.savefig(buf := __import__('io').BytesIO(), format='png', dpi=100, facecolor="#0a0a0f")
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.read(), dtype=np.uint8), cv2.IMREAD_COLOR)
    plt.close(fig)
    return img


def _plot_bev_tracks(df, bev_w, bev_h):
    """Create debug scatter of BEV-transformed tracks."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    sample = df.sample(min(50000, len(df)))
    ax.scatter(sample["bev_x"], sample["bev_y"], c="cyan", s=0.5, alpha=0.3)
    ax.set_xlim(0, bev_w)
    ax.set_ylim(0, bev_h)
    ax.set_aspect("equal")
    ax.set_title(f"BEV Track Scatter ({bev_w}x{bev_h})")
    ax.invert_yaxis()
    ax.set_facecolor("#0a0a0f")
    fig.patch.set_facecolor("#0a0a0f")
    ax.tick_params(colors="white")
    ax.title.set_color("white")

    fig.tight_layout()
    fig.savefig(buf := __import__('io').BytesIO(), format='png', dpi=100, facecolor="#0a0a0f")
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.read(), dtype=np.uint8), cv2.IMREAD_COLOR)
    plt.close(fig)
    return img


@ToolRegistry.register("calibrate_from_person_height")
def calibrate_from_person_height(state, config) -> ToolResult:
    """t03: BEV calibration from person-height regression.

    Uses bbox heights at different y-positions to fit a vanishing point model,
    then computes a homography for pixel→BEV transformation.
    """
    df = state.raw_tracks
    H_img, W_img = state.frame_shape[:2]

    # Step 1: Collect bbox height samples at various y positions
    good = df[(df["confidence"] > 0.5) & (df["bbox_h"] > 20)].copy()

    n_bands = 20
    band_height = H_img / n_bands

    y_positions = []
    px_heights = []

    for band in range(n_bands):
        y_lo = band * band_height
        y_hi = (band + 1) * band_height
        band_data = good[(good["y_center"] >= y_lo) & (good["y_center"] < y_hi)]

        if len(band_data) >= 5:
            y_positions.append(float(band_data["y_center"].median()))
            px_heights.append(float(band_data["bbox_h"].median()))

    y_positions = np.array(y_positions)
    px_heights = np.array(px_heights)

    if len(y_positions) < 4:
        return _fallback_simple_scaling(state, config)

    # Step 2: Fit perspective model
    # Model: px_height = K / (y - y_vanishing)
    def residual(params):
        K, y_vp = params
        predicted = K / (y_positions - y_vp + 1e-6)
        return predicted - px_heights

    y_vp_init = -H_img * 0.5
    K_init = float(np.mean(px_heights * (y_positions - y_vp_init)))

    result = least_squares(
        residual,
        [K_init, y_vp_init],
        bounds=([0, -H_img * 5], [K_init * 10, H_img * 0.3]),
    )
    K_fit, y_vp_fit = result.x

    # Sanity check: if vanishing point is too far away, perspective effect
    # is negligible (camera looking nearly straight down). Fall back to
    # simple scaling which produces a much more usable BEV.
    fit_rmse = float(np.mean(result.fun**2) ** 0.5)
    vp_distance = abs(y_vp_fit)
    if vp_distance > H_img * 3 or fit_rmse > np.mean(px_heights) * 0.5:
        logger.warning(
            f"Poor perspective fit (y_vp={y_vp_fit:.0f}, rmse={fit_rmse:.1f}). "
            f"Camera likely near-overhead. Using simple scaling."
        )
        return _fallback_simple_scaling(state, config)

    # Step 3: Estimate focal length
    focal_length_px = K_fit / AVERAGE_PERSON_HEIGHT_M

    # Step 4: Compute ground plane homography
    y_lo = max(float(y_positions.min()), H_img * 0.3)
    y_hi = min(float(y_positions.max()), H_img * 0.95)

    src_points = np.array(
        [
            [W_img * 0.2, y_lo],
            [W_img * 0.8, y_lo],
            [W_img * 0.8, y_hi],
            [W_img * 0.2, y_hi],
        ],
        dtype=np.float32,
    )

    bev_resolution = config.bev_resolution

    dst_points = []
    for sx, sy in src_points:
        dist_at_y = abs(sy - y_vp_fit) * AVERAGE_PERSON_HEIGHT_M
        x_offset_m = (sx - W_img / 2) * dist_at_y / focal_length_px
        bev_x = (x_offset_m / bev_resolution) + 500
        bev_y = dist_at_y / bev_resolution
        dst_points.append([bev_x, bev_y])

    dst_points = np.array(dst_points, dtype=np.float32)

    homography, _ = cv2.findHomography(src_points, dst_points)

    # Determine BEV image size
    corners = np.array([[0, 0], [W_img, 0], [W_img, H_img], [0, H_img]], dtype=np.float32)
    corners_h = np.hstack([corners, np.ones((4, 1))]).T
    bev_corners = (homography @ corners_h).T
    bev_corners = bev_corners[:, :2] / bev_corners[:, 2:3]

    bev_w = int(bev_corners[:, 0].max() - bev_corners[:, 0].min()) + 1
    bev_h = int(bev_corners[:, 1].max() - bev_corners[:, 1].min()) + 1
    bev_w = min(max(bev_w, 200), 2500)
    bev_h = min(max(bev_h, 200), 2500)

    state.homography_matrix = homography
    state.bev_scale = bev_resolution
    state.bev_size = (bev_w, bev_h)
    state.calibration_method = "person_height"

    # Step 5: Transform all tracks to BEV
    pts = df[["x_center", "y_center"]].values.astype(np.float32)
    pts_h = np.hstack([pts, np.ones((len(pts), 1))])
    bev = (homography @ pts_h.T).T
    bev = bev[:, :2] / bev[:, 2:3]

    df["bev_x"] = bev[:, 0]
    df["bev_y"] = bev[:, 1]
    df["bev_x_meters"] = bev[:, 0] * bev_resolution
    df["bev_y_meters"] = bev[:, 1] * bev_resolution

    # Recompute speed in meters/second
    df["bev_dx"] = df.groupby("track_id")["bev_x_meters"].diff().fillna(0)
    df["bev_dy"] = df.groupby("track_id")["bev_y_meters"].diff().fillna(0)
    df["speed_m_s"] = np.sqrt(df["bev_dx"] ** 2 + df["bev_dy"] ** 2) / df["dt"].clip(lower=1e-6)

    # Step 6: Validation
    fit_residual = float(np.mean(result.fun**2) ** 0.5)

    # Warp reference frame for debug
    debug_artifacts = {
        "height_regression": _plot_height_regression(y_positions, px_heights, K_fit, y_vp_fit),
        "bev_track_scatter": _plot_bev_tracks(df, bev_w, bev_h),
    }

    if state.reference_frame is not None:
        bev_image = cv2.warpPerspective(state.reference_frame, homography, (bev_w, bev_h))
        debug_artifacts["bev_reference_frame"] = bev_image

    return ToolResult(
        success=True,
        data={
            "focal_length_px": float(focal_length_px),
            "vanishing_point_y": float(y_vp_fit),
            "bev_size": (bev_w, bev_h),
            "bev_resolution": bev_resolution,
            "fit_residual": fit_residual,
            "n_height_samples": len(y_positions),
        },
        message=(
            f"Calibrated BEV {bev_w}x{bev_h} @ {bev_resolution}m/px "
            f"from {len(y_positions)} height bands, f={focal_length_px:.0f}px"
        ),
        debug_artifacts=debug_artifacts,
    )
