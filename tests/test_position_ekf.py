from __future__ import annotations

import numpy as np
import pytest

from backend.fusion.position_ekf import PositionEkf2D


def test_position_ekf_reduces_stationary_measurement_jitter() -> None:
    rng = np.random.default_rng(7)
    measurements = rng.normal(loc=(1.0, 2.0), scale=(0.12, 0.28), size=(200, 2))
    ekf = PositionEkf2D(acceleration_noise_mps2=0.35)
    estimates = []

    for index, measurement in enumerate(measurements):
        estimate = ekf.update(
            timestamp_us=index * 100_000,
            position_xy_m=(float(measurement[0]), float(measurement[1])),
            measurement_sigma_m=0.3,
        )
        estimates.append((estimate.x_m, estimate.y_m))

    filtered = np.asarray(estimates[50:])
    raw = measurements[50:]
    assert filtered[:, 0].std() < raw[:, 0].std() * 0.5
    assert filtered[:, 1].std() < raw[:, 1].std() * 0.5
    assert filtered.mean(axis=0) == pytest.approx((1.0, 2.0), abs=0.08)


def test_position_ekf_rejects_large_single_sample_jump() -> None:
    ekf = PositionEkf2D(acceleration_noise_mps2=0.3)
    for index in range(20):
        estimate = ekf.update(index * 100_000, (1.0, 1.0), 0.2)

    rejected = ekf.update(2_000_000, (8.0, -5.0), 0.2)

    assert rejected.measurement_accepted is False
    assert rejected.x_m == pytest.approx(estimate.x_m, abs=0.05)
    assert rejected.y_m == pytest.approx(estimate.y_m, abs=0.05)


def test_position_ekf_tracks_sustained_motion() -> None:
    ekf = PositionEkf2D(acceleration_noise_mps2=1.0)
    estimate = None
    for index in range(40):
        x_m = index * 0.05
        estimate = ekf.update(index * 100_000, (x_m, 0.5), 0.2)

    assert estimate is not None
    assert estimate.x_m == pytest.approx(1.95, abs=0.2)
    assert estimate.y_m == pytest.approx(0.5, abs=0.1)
    assert estimate.velocity_x_mps == pytest.approx(0.5, abs=0.2)


def test_position_ekf_uses_zupt_to_stop_false_coasting() -> None:
    ekf = PositionEkf2D(acceleration_noise_mps2=0.5)
    moving = None
    for index in range(20):
        moving = ekf.update(
            index * 100_000,
            (index * 0.08, 1.0),
            0.15,
        )

    assert moving is not None
    assert moving.velocity_x_mps > 0.4

    stopped = None
    for index in range(1, 4):
        stopped = ekf.apply_zero_velocity(1_900_000 + index * 20_000)

    assert stopped is not None
    assert stopped.velocity_x_mps == pytest.approx(0.0, abs=0.03)
    assert stopped.velocity_y_mps == pytest.approx(0.0, abs=0.03)


def test_position_ekf_ignores_zupt_before_uwb_initialization() -> None:
    ekf = PositionEkf2D()

    assert ekf.apply_zero_velocity(100_000) is None
