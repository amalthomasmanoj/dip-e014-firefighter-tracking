from __future__ import annotations

import pytest

from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.models.measurements import ImuMeasurement


def test_imu_only_measurement_emits_live_state() -> None:
    estimator = DemoSensorEstimator()
    sample = ImuMeasurement(
        timestamp_us=123456789,
        node_id="esp32_lab_01",
        sequence_number=102489,
        ax_mps2=-1.74,
        ay_mps2=0.0,
        az_mps2=9.73,
        gx_radps=-0.029,
        gy_radps=0.049,
        gz_radps=-0.044,
    )

    state = estimator.update(sample)

    assert state is not None
    assert state.timestamp_us == 123456789
    assert state.position_m.x == pytest.approx(0.0)
    assert state.position_m.y == pytest.approx(0.0)
    assert state.status.uwb_available is False
    assert state.status.active_anchor_count == 0
    assert state.activity.posture == "standing"
    assert state.uncertainty.sigma_x_m == pytest.approx(5.0)


def test_imu_only_state_can_be_disabled_for_simulation_startup() -> None:
    estimator = DemoSensorEstimator(emit_imu_only_state=False)
    sample = ImuMeasurement(
        timestamp_us=1,
        node_id="esp32_lab_01",
        sequence_number=1,
        ax_mps2=0.0,
        ay_mps2=0.0,
        az_mps2=9.81,
        gx_radps=0.0,
        gy_radps=0.0,
        gz_radps=0.0,
    )

    assert estimator.update(sample) is None
