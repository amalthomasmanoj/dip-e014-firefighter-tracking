from __future__ import annotations

from collections.abc import Mapping
from math import sqrt

from backend.uwb.anchors import Anchor


def trilaterate_2d(anchors: list[Anchor], ranges_m: Mapping[str, float]) -> tuple[float, float]:
    """Estimate x,y from three or more known anchors using linearized least squares."""
    usable = [anchor for anchor in anchors if anchor.anchor_id in ranges_m]
    if len(usable) < 3:
        raise ValueError("at least three anchor ranges are required")

    reference = usable[0]
    r0 = ranges_m[reference.anchor_id]
    rows: list[tuple[float, float]] = []
    rhs: list[float] = []

    for anchor in usable[1:]:
        ri = ranges_m[anchor.anchor_id]
        rows.append((2.0 * (anchor.x_m - reference.x_m), 2.0 * (anchor.y_m - reference.y_m)))
        rhs.append(
            r0**2
            - ri**2
            - reference.x_m**2
            + anchor.x_m**2
            - reference.y_m**2
            + anchor.y_m**2
        )

    a00 = sum(x * x for x, _y in rows)
    a01 = sum(x * y for x, y in rows)
    a11 = sum(y * y for _x, y in rows)
    b0 = sum(x * value for (x, _y), value in zip(rows, rhs, strict=True))
    b1 = sum(y * value for (_x, y), value in zip(rows, rhs, strict=True))
    det = a00 * a11 - a01 * a01
    if abs(det) < 1e-12:
        raise ValueError("anchor geometry is singular")

    x = (b0 * a11 - b1 * a01) / det
    y = (a00 * b1 - a01 * b0) / det
    if not all(value == value and abs(value) != float("inf") for value in (x, y)):
        raise ValueError("trilateration produced a non-finite result")
    return x, y


def distance_2d(anchor: Anchor, point: tuple[float, float]) -> float:
    return sqrt((anchor.x_m - point[0]) ** 2 + (anchor.y_m - point[1]) ** 2)

