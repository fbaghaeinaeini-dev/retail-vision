"""Core data models for the agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standard return type for all pipeline tools."""

    success: bool
    data: Any = None
    debug_artifacts: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    duration_seconds: float = 0.0


@dataclass
class ZoneCandidate:
    """A discovered zone candidate from one strategy."""

    zone_id: str
    polygon_bev: list[list[float]]  # BEV polygon vertices
    centroid_bev: list[float]       # [x, y] in BEV coordinates
    area_m2: float = 0.0
    confidence: float = 0.0
    strategy: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class FusedZone:
    """A zone after ensemble fusion."""

    zone_id: str
    polygon_bev: list[list[float]]
    centroid_bev: list[float]
    area_m2: float = 0.0
    bbox_pixel: list[float] = field(default_factory=list)  # [x1, y1, x2, y2]
    strategy_agreement: int = 0
    contributing_strategies: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class DwellPoint:
    """A detected dwell event."""

    track_id: int
    centroid_bev: list[float]  # [x, y] in BEV meters
    duration_seconds: float
    confinement_radius_m: float
    start_frame: int
    end_frame: int
    curvature: float = 0.0
