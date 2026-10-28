from __future__ import annotations

import math

import pytest

from backend.imu.heading import (
    GyroYawIntegrator,
    heading_to_quaternion_xyzw,
    wrap_to_pi,
)
from backend.models.measurements import ImuMeasurement


def imu_sample(timestamp_us: int, gz_radps: float) -> ImuMeasurement:
    return ImuMeasurement(
        timestamp_us=timestamp_us,
        node_id="wearable_01",
        sequence_number=timestamp_us,
        ax_mps2=0.0,
        ay_mps2=0.0,
        az_mps2=9.81,
        gx_radps=0.0,
        gy_radps=0.0,
        gz_radps=gz_radps,
    )


def test_wrap_to_pi_normalizes_full_turns() -> None:
    assert wrap_to_pi(0.0) == pytest.approx(0.0)
    assert wrap_to_pi(3.0 * math.pi) == pytest.approx(-math.pi)
    assert wrap_to_pi(-3.0 * math.pi) == pytest.approx(-math.pi)


def test_integrator_accumulates_constant_yaw_rate() -> None:
    integrator = GyroYawIntegrator(calibration_samples=0)
    # 1 rad/s for 1 s in 10 steps
    integrator.update(imu_sample(0, 1.0))
    for step in range(1, 11):
        heading = integrator.update(imu_sample(step * 100_000, 1.0))

    assert heading == pytest.approx(1.0, abs=1e-9)


def test_integrator_wraps_past_half_turn() -> None:
    integrator = GyroYawIntegrator(calibration_samples=0)
    integrator.update(imu_sample(0, math.pi))
    heading = integrator.update(imu_sample(400_000, math.pi))

    # pi * 0.4 s past... accumulate to beyond pi over several steps
    for step in range(2, 10):
        heading = integrator.update(imu_sample(step * 400_000, math.pi))

    assert -math.pi <= heading < math.pi


def test_integrator_ignores_non_monotonic_samples() -> None:
    integrator = GyroYawIntegrator(calibration_samples=0)
    integrator.update(imu_sample(1_000_000, 1.0))
    integrator.update(imu_sample(1_100_000, 1.0))
    before = integrator.heading_rad

    integrator.update(imu_sample(900_000, 1.0))

    assert integrator.heading_rad == pytest.approx(before)


def test_integrator_skips_integration_across_long_dropout() -> None:
    integrator = GyroYawIntegrator(max_dt_s=0.5, calibration_samples=0)
    integrator.update(imu_sample(0, 1.0))
    integrator.update(imu_sample(2_000_000, 1.0))

    assert integrator.heading_rad == pytest.approx(0.0)


def test_reset_returns_to_initial_heading() -> None:
    integrator = GyroYawIntegrator(initial_heading_rad=0.5, calibration_samples=0)
    integrator.update(imu_sample(0, 1.0))
    integrator.update(imu_sample(100_000, 1.0))
    integrator.reset()

    assert integrator.heading_rad == pytest.approx(0.5)


def test_stationary_window_calibrates_gyro_bias_before_integration() -> None:
    integrator = GyroYawIntegrator(calibration_samples=3)
    for timestamp in (0, 20_000, 40_000):
        integrator.update(imu_sample(timestamp, 0.04))

    assert integrator.calibrated is True
    assert integrator.gyro_bias_radps == pytest.approx(0.04)

    integrator.update(imu_sample(140_000, 1.04))
    assert integrator.heading_rad == pytest.approx(0.1)


def test_alignment_keeps_bias_and_sets_world_heading() -> None:
    integrator = GyroYawIntegrator(calibration_samples=1)
    integrator.update(imu_sample(0, 0.02))

    integrator.align(math.pi / 2)
    integrator.update(imu_sample(100_000, 0.02))
    integrator.update(imu_sample(200_000, 1.02))

    assert integrator.calibrated is True
    assert integrator.heading_rad == pytest.approx(math.pi / 2 + 0.1)


def test_heading_quaternion_round_trips_through_atan2() -> None:
    for heading_rad in (-2.0, -0.4, 0.0, 0.7, 2.9):
        x, y, z, w = heading_to_quaternion_xyzw(heading_rad)
        recovered = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        assert recovered == pytest.approx(heading_rad, abs=1e-9)
