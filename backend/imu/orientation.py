from __future__ import annotations

from backend.models.state import Quaternion


def identity_orientation() -> Quaternion:
    return Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)

