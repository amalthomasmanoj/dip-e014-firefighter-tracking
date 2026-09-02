from __future__ import annotations

import pytest

from backend.uwb.anchors import Anchor
from backend.uwb.trilateration import distance_2d, trilaterate_2d


def test_trilateration_known_geometry() -> None:
    anchors = [
        Anchor("A1", 0.0, 0.0),
        Anchor("A2", 4.0, 0.0),
        Anchor("A3", 0.0, 3.0),
    ]
    tag = (1.0, 1.0)
    ranges = {anchor.anchor_id: distance_2d(anchor, tag) for anchor in anchors}

    x, y = trilaterate_2d(anchors, ranges)

    assert x == pytest.approx(1.0)
    assert y == pytest.approx(1.0)

