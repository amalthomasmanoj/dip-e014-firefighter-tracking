from __future__ import annotations

from backend.uwb.anchors import Anchor
from backend.uwb.trilateration import distance_2d


def range_residual(anchor: Anchor, position_xy: tuple[float, float], measured_range_m: float) -> float:
    return measured_range_m - distance_2d(anchor, position_xy)

