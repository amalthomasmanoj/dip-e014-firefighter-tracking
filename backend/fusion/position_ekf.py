from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PositionEstimate:
    x_m: float
    y_m: float
    velocity_x_mps: float
    velocity_y_mps: float
    sigma_x_m: float
    sigma_y_m: float
    measurement_accepted: bool


class PositionEkf2D:
    """Constant-velocity 2-D EKF for smoothing derived UWB positions.

    This intentionally filters only estimator output. Raw range measurements
    remain unchanged in ingestion and the live range tracker.
    """

    def __init__(
        self,
        acceleration_noise_mps2: float = 0.8,
        innovation_gate_squared: float = 9.21,
        low_speed_deadband_mps: float = 0.08,
    ) -> None:
        if acceleration_noise_mps2 <= 0.0:
            raise ValueError("acceleration noise must be positive")
        if innovation_gate_squared <= 0.0:
            raise ValueError("innovation gate must be positive")
        if low_speed_deadband_mps < 0.0:
            raise ValueError("low-speed deadband cannot be negative")

        self._acceleration_noise_mps2 = acceleration_noise_mps2
        self._innovation_gate_squared = innovation_gate_squared
        self._low_speed_deadband_mps = low_speed_deadband_mps
        self._state: np.ndarray | None = None
        self._covariance: np.ndarray | None = None
        self._timestamp_us: int | None = None

    def update(
        self,
        timestamp_us: int,
        position_xy_m: tuple[float, float],
        measurement_sigma_m: float,
    ) -> PositionEstimate:
        if measurement_sigma_m <= 0.0:
            raise ValueError("measurement sigma must be positive")

        measurement = np.asarray(position_xy_m, dtype=float)
        if measurement.shape != (2,) or not np.all(np.isfinite(measurement)):
            raise ValueError("position measurement must contain two finite values")

        if self._state is None or self._covariance is None or self._timestamp_us is None:
            variance = measurement_sigma_m**2
            self._state = np.array([measurement[0], measurement[1], 0.0, 0.0])
            self._covariance = np.diag([variance, variance, 1.0, 1.0])
            self._timestamp_us = timestamp_us
            return self._estimate(measurement_accepted=True)

        dt_s = (timestamp_us - self._timestamp_us) / 1_000_000.0
        if dt_s <= 0.0:
            return self._estimate(measurement_accepted=False)
        dt_s = min(dt_s, 1.0)
        self._predict(dt_s)
        self._timestamp_us = timestamp_us

        observation = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ]
        )
        measurement_covariance = np.eye(2) * measurement_sigma_m**2
        innovation = measurement - observation @ self._state
        innovation_covariance = (
            observation @ self._covariance @ observation.T + measurement_covariance
        )
        mahalanobis_squared = float(
            innovation.T @ np.linalg.solve(innovation_covariance, innovation)
        )

        accepted = mahalanobis_squared <= self._innovation_gate_squared
        if accepted:
            kalman_gain = (
                self._covariance
                @ observation.T
                @ np.linalg.inv(innovation_covariance)
            )
            self._state = self._state + kalman_gain @ innovation
            identity = np.eye(4)
            correction = identity - kalman_gain @ observation
            self._covariance = (
                correction @ self._covariance @ correction.T
                + kalman_gain @ measurement_covariance @ kalman_gain.T
            )

        if np.hypot(self._state[2], self._state[3]) < self._low_speed_deadband_mps:
            self._state[2:] = 0.0

        return self._estimate(measurement_accepted=accepted)

    def _predict(self, dt_s: float) -> None:
        assert self._state is not None
        assert self._covariance is not None
        transition = np.array(
            [
                [1.0, 0.0, dt_s, 0.0],
                [0.0, 1.0, 0.0, dt_s],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        dt2 = dt_s**2
        noise_mapping = np.array(
            [
                [dt2 / 2.0, 0.0],
                [0.0, dt2 / 2.0],
                [dt_s, 0.0],
                [0.0, dt_s],
            ]
        )
        acceleration_covariance = (
            np.eye(2) * self._acceleration_noise_mps2**2
        )
        self._state = transition @ self._state
        self._covariance = (
            transition @ self._covariance @ transition.T
            + noise_mapping @ acceleration_covariance @ noise_mapping.T
        )

    def _estimate(self, measurement_accepted: bool) -> PositionEstimate:
        assert self._state is not None
        assert self._covariance is not None
        return PositionEstimate(
            x_m=float(self._state[0]),
            y_m=float(self._state[1]),
            velocity_x_mps=float(self._state[2]),
            velocity_y_mps=float(self._state[3]),
            sigma_x_m=float(np.sqrt(max(self._covariance[0, 0], 0.0))),
            sigma_y_m=float(np.sqrt(max(self._covariance[1, 1], 0.0))),
            measurement_accepted=measurement_accepted,
        )
