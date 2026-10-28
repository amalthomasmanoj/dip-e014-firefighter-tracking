from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

from backend.models.measurements import ImuMeasurement

Posture = Literal["standing", "crouching", "lying_down"]
Motion = Literal["stationary", "walking"]

DEFAULT_LYING_TILT_THRESHOLD_RAD = 1.22
DEFAULT_UPRIGHT_TILT_THRESHOLD_RAD = 0.96
DEFAULT_WALKING_SPEED_THRESHOLD_MPS = 0.2
DEFAULT_POSTURE_DWELL_US = 2_000_000


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
    lying_tilt_threshold_rad: float = DEFAULT_LYING_TILT_THRESHOLD_RAD,
    walking_speed_threshold_mps: float = DEFAULT_WALKING_SPEED_THRESHOLD_MPS,
) -> ActivityEstimate:
    """Classify one waist sample without claiming a fall event."""
    if not 0.0 < lying_tilt_threshold_rad <= math.pi:
        raise ValueError("lying threshold must be within (0, pi]")

    tilt_rad = tilt_from_vertical_rad(sample)

    if tilt_rad >= lying_tilt_threshold_rad:
        posture: Posture = "lying_down"
        posture_margin = abs(tilt_rad - lying_tilt_threshold_rad)
    else:
        posture = "standing"
        posture_margin = abs(tilt_rad - lying_tilt_threshold_rad)

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


class WaistPostureClassifier:
    """Filtered, hysteretic standing/lying posture for a waist-mounted IMU."""

    def __init__(
        self,
        lying_tilt_threshold_rad: float = DEFAULT_LYING_TILT_THRESHOLD_RAD,
        upright_tilt_threshold_rad: float = DEFAULT_UPRIGHT_TILT_THRESHOLD_RAD,
        dwell_us: int = DEFAULT_POSTURE_DWELL_US,
        max_sample_gap_us: int = 500_000,
        low_pass_alpha: float = 0.2,
        walking_speed_threshold_mps: float = DEFAULT_WALKING_SPEED_THRESHOLD_MPS,
    ) -> None:
        if not 0.0 <= upright_tilt_threshold_rad < lying_tilt_threshold_rad <= math.pi:
            raise ValueError("posture thresholds must provide upright/lying hysteresis")
        if dwell_us < 0 or max_sample_gap_us <= 0:
            raise ValueError("posture timing values must be positive")
        if not 0.0 < low_pass_alpha <= 1.0:
            raise ValueError("low_pass_alpha must be within (0, 1]")
        self._lying_tilt_threshold_rad = lying_tilt_threshold_rad
        self._upright_tilt_threshold_rad = upright_tilt_threshold_rad
        self._dwell_us = dwell_us
        self._max_sample_gap_us = max_sample_gap_us
        self._low_pass_alpha = low_pass_alpha
        self._walking_speed_threshold_mps = walking_speed_threshold_mps
        self.reset()

    def classify(
        self,
        sample: ImuMeasurement,
        speed_mps: float,
        zupt_active: bool,
    ) -> ActivityEstimate:
        instantaneous = classify_activity(
            sample=sample,
            speed_mps=speed_mps,
            zupt_active=zupt_active,
            lying_tilt_threshold_rad=self._lying_tilt_threshold_rad,
            walking_speed_threshold_mps=self._walking_speed_threshold_mps,
        )
        accel_norm = math.sqrt(
            sample.ax_mps2**2 + sample.ay_mps2**2 + sample.az_mps2**2
        )
        reliable_gravity = abs(accel_norm - 9.80665) <= 2.0
        if reliable_gravity:
            if self._last_timestamp_us is not None and not (
                0 < sample.timestamp_us - self._last_timestamp_us <= self._max_sample_gap_us
            ):
                self._candidate = None
                self._candidate_since_us = None
            self._last_timestamp_us = sample.timestamp_us
            tilt_rad = tilt_from_vertical_rad(sample)
            self._filtered_tilt_rad = (
                tilt_rad
                if self._filtered_tilt_rad is None
                else self._low_pass_alpha * tilt_rad
                + (1.0 - self._low_pass_alpha) * self._filtered_tilt_rad
            )
            target = self._posture
            if self._posture == "standing" and self._filtered_tilt_rad >= self._lying_tilt_threshold_rad:
                target = "lying_down"
            elif self._posture == "lying_down" and self._filtered_tilt_rad <= self._upright_tilt_threshold_rad:
                target = "standing"

            if target == self._posture:
                self._candidate = None
                self._candidate_since_us = None
            elif target != self._candidate:
                self._candidate = target
                self._candidate_since_us = sample.timestamp_us
            elif (
                self._candidate_since_us is not None
                and sample.timestamp_us - self._candidate_since_us >= self._dwell_us
            ):
                self._posture = target
                self._candidate = None
                self._candidate_since_us = None
        else:
            self._candidate = None
            self._candidate_since_us = None

        return ActivityEstimate(
            posture=self._posture,
            motion=instantaneous.motion,
            confidence=instantaneous.confidence if reliable_gravity else 0.0,
        )

    def reset(self) -> None:
        self._posture: Posture = "standing"
        self._filtered_tilt_rad: float | None = None
        self._candidate: Posture | None = None
        self._candidate_since_us: int | None = None
        self._last_timestamp_us: int | None = None


TiltActivityClassifier = WaistPostureClassifier
