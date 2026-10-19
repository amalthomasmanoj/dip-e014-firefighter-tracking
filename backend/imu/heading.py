from __future__ import annotations

import math
from typing import Protocol

from backend.models.measurements import ImuMeasurement


class HeadingEstimator(Protocol):
    """Seam for replacing heading estimation without touching the estimator.

    Implementations keep their own internal state and return the current
    heading in radians, measured in the world frame defined by
    docs/coordinate_frames.md: 0 along +x, increasing towards +y.
    """

    def update(self, sample: ImuMeasurement) -> float:
        """Consume one IMU sample and return the current heading in radians."""

    def reset(self) -> None:
        """Drop accumulated state."""


def wrap_to_pi(angle_rad: float) -> float:
    """Normalize an angle to the half-open interval [-pi, pi)."""
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi


class GyroYawIntegrator:
    """Baseline heading: integrate the body-z gyro rate over sample intervals.

    This is the behaviour the demo estimator shipped with, extracted so it can
    be swapped for a real complementary/Madgwick/Mahony filter. It drifts; it
    has no magnetometer and no gravity correction, so it is a bring-up
    reference only, not a finished heading solution.
    """

    def __init__(self, initial_heading_rad: float = 0.0, max_dt_s: float = 0.5) -> None:
        if max_dt_s <= 0.0:
            raise ValueError("max_dt_s must be positive")
        self._initial_heading_rad = initial_heading_rad
        self._max_dt_s = max_dt_s
        self._heading_rad = initial_heading_rad
        self._last_timestamp_us: int | None = None

    @property
    def heading_rad(self) -> float:
        return self._heading_rad

    def update(self, sample: ImuMeasurement) -> float:
        if self._last_timestamp_us is not None:
            dt_s = (sample.timestamp_us - self._last_timestamp_us) / 1_000_000
            # Reject non-monotonic samples and gaps that would integrate a
            # stale rate across a dropout.
            if 0.0 < dt_s <= self._max_dt_s:
                self._heading_rad = wrap_to_pi(
                    self._heading_rad + sample.gz_radps * dt_s
                )
        self._last_timestamp_us = sample.timestamp_us
        return self._heading_rad

    def reset(self) -> None:
        self._heading_rad = self._initial_heading_rad
        self._last_timestamp_us = None


def heading_to_quaternion_xyzw(heading_rad: float) -> tuple[float, float, float, float]:
    """Convert a yaw-only heading to the contract's (x, y, z, w) quaternion."""
    half = heading_rad / 2.0
    return (0.0, 0.0, math.sin(half), math.cos(half))
