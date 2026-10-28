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

    def align(self, heading_rad: float) -> None:
        """Set the current world-frame heading without discarding calibration."""


def wrap_to_pi(angle_rad: float) -> float:
    """Normalize an angle to the half-open interval [-pi, pi)."""
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi


class GyroYawIntegrator:
    """Bias-calibrated relative heading from a waist-frame body-z gyro.

    This deliberately does not claim magnetic north. The wearer faces a known
    building direction and aligns the session after the stationary bias window.
    """

    def __init__(
        self,
        initial_heading_rad: float = 0.0,
        max_dt_s: float = 0.5,
        calibration_samples: int = 50,
        stationary_gyro_threshold_radps: float = 0.15,
        gravity_tolerance_mps2: float = 1.5,
    ) -> None:
        if max_dt_s <= 0.0:
            raise ValueError("max_dt_s must be positive")
        if calibration_samples < 0:
            raise ValueError("calibration_samples cannot be negative")
        if stationary_gyro_threshold_radps <= 0.0 or gravity_tolerance_mps2 <= 0.0:
            raise ValueError("stationary thresholds must be positive")
        if not math.isfinite(initial_heading_rad):
            raise ValueError("initial heading must be finite")
        self._initial_heading_rad = wrap_to_pi(initial_heading_rad)
        self._max_dt_s = max_dt_s
        self._calibration_samples = calibration_samples
        self._stationary_gyro_threshold_radps = stationary_gyro_threshold_radps
        self._gravity_tolerance_mps2 = gravity_tolerance_mps2
        self._heading_rad = self._initial_heading_rad
        self._last_timestamp_us: int | None = None
        self._bias_samples: list[float] = []
        self._gyro_bias_radps = 0.0
        self._calibrated = calibration_samples == 0

    @property
    def heading_rad(self) -> float:
        return self._heading_rad

    @property
    def calibrated(self) -> bool:
        return self._calibrated

    @property
    def gyro_bias_radps(self) -> float:
        return self._gyro_bias_radps

    def _stationary(self, sample: ImuMeasurement) -> bool:
        gyro_norm = math.sqrt(
            sample.gx_radps**2 + sample.gy_radps**2 + sample.gz_radps**2
        )
        accel_norm = math.sqrt(
            sample.ax_mps2**2 + sample.ay_mps2**2 + sample.az_mps2**2
        )
        return (
            gyro_norm <= self._stationary_gyro_threshold_radps
            and abs(accel_norm - 9.80665) <= self._gravity_tolerance_mps2
        )

    def update(self, sample: ImuMeasurement) -> float:
        if not self._calibrated:
            if self._stationary(sample):
                self._bias_samples.append(sample.gz_radps)
                if len(self._bias_samples) >= self._calibration_samples:
                    self._gyro_bias_radps = sum(self._bias_samples) / len(self._bias_samples)
                    self._calibrated = True
                    self._last_timestamp_us = sample.timestamp_us
            else:
                self._bias_samples.clear()
            return self._heading_rad

        if self._last_timestamp_us is not None:
            dt_s = (sample.timestamp_us - self._last_timestamp_us) / 1_000_000
            if 0.0 < dt_s <= self._max_dt_s:
                self._heading_rad = wrap_to_pi(
                    self._heading_rad
                    + (sample.gz_radps - self._gyro_bias_radps) * dt_s
                )
            if dt_s > 0.0:
                self._last_timestamp_us = sample.timestamp_us
        else:
            self._last_timestamp_us = sample.timestamp_us
        return self._heading_rad

    def align(self, heading_rad: float) -> None:
        if not math.isfinite(heading_rad):
            raise ValueError("heading must be finite")
        self._heading_rad = wrap_to_pi(heading_rad)
        self._last_timestamp_us = None

    def reset(self) -> None:
        self._heading_rad = self._initial_heading_rad
        self._last_timestamp_us = None
        self._bias_samples.clear()
        self._gyro_bias_radps = 0.0
        self._calibrated = self._calibration_samples == 0


def heading_to_quaternion_xyzw(heading_rad: float) -> tuple[float, float, float, float]:
    """Convert a yaw-only heading to the contract's (x, y, z, w) quaternion."""
    half = heading_rad / 2.0
    return (0.0, 0.0, math.sin(half), math.cos(half))
