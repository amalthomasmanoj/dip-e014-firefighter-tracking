from __future__ import annotations

from backend.imu.zupt_detector import detect_zupt_window, is_stationary_sample
from backend.models.measurements import ImuMeasurement


def sample(
    ax: float = 0.0,
    ay: float = 0.0,
    az: float = 9.80665,
    gx: float = 0.0,
    gy: float = 0.0,
    gz: float = 0.0,
) -> ImuMeasurement:
    return ImuMeasurement(
        timestamp_us=1,
        node_id="wearable_01",
        sequence_number=1,
        ax_mps2=ax,
        ay_mps2=ay,
        az_mps2=az,
        gx_radps=gx,
        gy_radps=gy,
        gz_radps=gz,
    )


def test_stationary_sample_detected() -> None:
    assert is_stationary_sample(sample())


def test_moving_sample_rejected() -> None:
    assert not is_stationary_sample(sample(gx=0.3))


def test_zupt_window_detected() -> None:
    assert detect_zupt_window([sample(), sample(), sample()])

