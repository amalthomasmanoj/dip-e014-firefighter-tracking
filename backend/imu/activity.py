from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

from backend.models.measurements import ImuMeasurement

Posture = Literal["standing", "crouching", "lying_down"]
Motion = Literal["stationary", "walking"]

DEFAULT_CROUCH_TILT_THRESHOLD_RAD = 0.65
DEFAULT_LYING_TILT_THRESHOLD_RAD = 1.22
DEFAULT_WALKING_SPEED_THRESHOLD_MPS = 0.2


@dataclass(frozen=True)
class ActivityEstimate:
    posture: Posture
    motion: Motion
    confidence: float


class ActivityClassifier(Protocol):
    """Seam for replacing posture/fall classification.

    Implementations may hold internal state (windows, filters, hysteresis) and
    must return one `ActivityEstimate` per call.
    """

    def classify(
        self,
        sample: ImuMeasurement,
        speed_mps: float,
        zupt_active: bool,
    ) -> ActivityEstimate:
        """Classify the current activity from one IMU sample and motion context."""

    def reset(self) -> None:
        """Drop accumulated state."""


def tilt_from_vertical_rad(sample: ImuMeasurement) -> float:
    """Angle between the sensor's measured acceleration and world up.

    While the wearer is near-stationary this is dominated by gravity, so it
    approximates trunk tilt: ~0 upright, ~pi/2 horizontal. Under strong
    linear acceleration it is not a reliable tilt estimate.
    """
    accel_norm = math.sqrt(
        sample.ax_mps2**2 + sample.ay_mps2**2 + sample.az_mps2**2
    )
    if accel_norm <= 1e-9:
        return 0.0
    vertical_fraction = max(-1.0, min(1.0, sample.az_mps2 / accel_norm))
    return math.acos(vertical_fraction)


def classify_activity(
    sample: ImuMeasurement,
    speed_mps: float,
    zupt_active: bool,
    crouch_tilt_threshold_rad: float = DEFAULT_CROUCH_TILT_THRESHOLD_RAD,
    lying_tilt_threshold_rad: float = DEFAULT_LYING_TILT_THRESHOLD_RAD,
    walking_speed_threshold_mps: float = DEFAULT_WALKING_SPEED_THRESHOLD_MPS,
) -> ActivityEstimate:
    """Classify coarse firefighter activity from generic IMU/state signals.

    Tilt bands only; this is a bring-up baseline, not validated fall
    detection. Replace it by passing a custom `ActivityClassifier` to the
    estimator rather than editing this function.
    """
    if lying_tilt_threshold_rad < crouch_tilt_threshold_rad:
        raise ValueError("lying threshold must be at or above the crouch threshold")

    tilt_rad = tilt_from_vertical_rad(sample)

    if tilt_rad >= lying_tilt_threshold_rad:
        posture: Posture = "lying_down"
        posture_margin = abs(tilt_rad - lying_tilt_threshold_rad)
    elif tilt_rad >= crouch_tilt_threshold_rad:
        posture = "crouching"
        posture_margin = min(
            abs(tilt_rad - crouch_tilt_threshold_rad),
            abs(tilt_rad - lying_tilt_threshold_rad),
        )
    else:
        posture = "standing"
        posture_margin = abs(tilt_rad - crouch_tilt_threshold_rad)

    motion: Motion = (
        "stationary" if zupt_active or speed_mps < walking_speed_threshold_mps else "walking"
    )

    motion_margin = abs(speed_mps - walking_speed_threshold_mps)
    posture_confidence = min(0.95, 0.55 + posture_margin)
    motion_confidence = 0.9 if zupt_active else min(0.95, 0.55 + motion_margin)
    confidence = max(0.0, min(0.95, min(posture_confidence, motion_confidence)))

    return ActivityEstimate(
        posture=posture,
        motion=motion,
        confidence=round(confidence, 3),
    )


class TiltActivityClassifier:
    """Default `ActivityClassifier` wrapping the stateless tilt bands."""

    def __init__(
        self,
        crouch_tilt_threshold_rad: float = DEFAULT_CROUCH_TILT_THRESHOLD_RAD,
        lying_tilt_threshold_rad: float = DEFAULT_LYING_TILT_THRESHOLD_RAD,
        walking_speed_threshold_mps: float = DEFAULT_WALKING_SPEED_THRESHOLD_MPS,
    ) -> None:
        self._crouch_tilt_threshold_rad = crouch_tilt_threshold_rad
        self._lying_tilt_threshold_rad = lying_tilt_threshold_rad
        self._walking_speed_threshold_mps = walking_speed_threshold_mps

    def classify(
        self,
        sample: ImuMeasurement,
        speed_mps: float,
        zupt_active: bool,
    ) -> ActivityEstimate:
        return classify_activity(
            sample=sample,
            speed_mps=speed_mps,
            zupt_active=zupt_active,
            crouch_tilt_threshold_rad=self._crouch_tilt_threshold_rad,
            lying_tilt_threshold_rad=self._lying_tilt_threshold_rad,
            walking_speed_threshold_mps=self._walking_speed_threshold_mps,
        )

    def reset(self) -> None:
        return None
