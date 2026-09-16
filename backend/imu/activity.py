from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from backend.models.measurements import ImuMeasurement

Posture = Literal["standing", "crouching"]
Motion = Literal["stationary", "walking"]


@dataclass(frozen=True)
class ActivityEstimate:
    posture: Posture
    motion: Motion
    confidence: float


def classify_activity(
    sample: ImuMeasurement,
    speed_mps: float,
    zupt_active: bool,
    crouch_tilt_threshold_rad: float = 0.65,
    walking_speed_threshold_mps: float = 0.2,
) -> ActivityEstimate:
    """Classify coarse firefighter activity from generic IMU/state signals."""
    accel_norm = math.sqrt(
        sample.ax_mps2**2 + sample.ay_mps2**2 + sample.az_mps2**2
    )
    if accel_norm <= 1e-9:
        tilt_rad = 0.0
    else:
        vertical_fraction = max(-1.0, min(1.0, sample.az_mps2 / accel_norm))
        tilt_rad = math.acos(vertical_fraction)

    posture: Posture = "crouching" if tilt_rad >= crouch_tilt_threshold_rad else "standing"
    motion: Motion = (
        "stationary" if zupt_active or speed_mps < walking_speed_threshold_mps else "walking"
    )

    posture_margin = abs(tilt_rad - crouch_tilt_threshold_rad)
    motion_margin = abs(speed_mps - walking_speed_threshold_mps)
    posture_confidence = min(0.95, 0.55 + posture_margin)
    motion_confidence = 0.9 if zupt_active else min(0.95, 0.55 + motion_margin)
    confidence = max(0.0, min(0.95, min(posture_confidence, motion_confidence)))

    return ActivityEstimate(
        posture=posture,
        motion=motion,
        confidence=round(confidence, 3),
    )
