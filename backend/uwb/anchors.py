from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    anchor_id: str
    x_m: float
    y_m: float
    z_m: float = 0.0


DEFAULT_ANCHORS = (
    Anchor("A1", 0.0, 0.0, 0.0),
    Anchor("A2", 8.0, 0.0, 0.0),
    Anchor("A3", 0.0, 6.0, 0.0),
)

