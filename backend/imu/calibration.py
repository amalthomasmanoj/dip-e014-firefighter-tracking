from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImuBias:
    ax_mps2: float = 0.0
    ay_mps2: float = 0.0
    az_mps2: float = 0.0
    gx_radps: float = 0.0
    gy_radps: float = 0.0
    gz_radps: float = 0.0

