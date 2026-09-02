from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Quaternion:
    x: float
    y: float
    z: float
    w: float


@dataclass(frozen=True)
class Uncertainty:
    sigma_x_m: float
    sigma_y_m: float
    sigma_z_m: float


@dataclass(frozen=True)
class SensorStatus:
    zupt_active: bool
    uwb_available: bool
    active_anchor_count: int


@dataclass(frozen=True)
class EstimatedState:
    timestamp_us: int
    position_m: Vector3
    velocity_mps: Vector3
    orientation_xyzw: Quaternion
    uncertainty: Uncertainty
    status: SensorStatus

    def to_dict(self) -> dict:
        return asdict(self)


def websocket_message(state: EstimatedState, source: str = "simulation") -> dict:
    return {
        "type": "estimated_state",
        "source": source,
        "state": state.to_dict(),
    }

