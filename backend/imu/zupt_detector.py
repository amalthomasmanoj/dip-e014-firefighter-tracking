from __future__ import annotations

from collections.abc import Iterable

from backend.models.measurements import ImuMeasurement


def is_stationary_sample(
    sample: ImuMeasurement,
    accel_norm_mps2: float = 9.80665,
    accel_tolerance_mps2: float = 0.35,
    gyro_threshold_radps: float = 0.08,
) -> bool:
    accel_norm = (
        sample.ax_mps2**2 + sample.ay_mps2**2 + sample.az_mps2**2
    ) ** 0.5
    gyro_norm = (
        sample.gx_radps**2 + sample.gy_radps**2 + sample.gz_radps**2
    ) ** 0.5
    return (
        abs(accel_norm - accel_norm_mps2) <= accel_tolerance_mps2
        and gyro_norm <= gyro_threshold_radps
    )


def detect_zupt_window(samples: Iterable[ImuMeasurement], min_stationary: int = 3) -> bool:
    count = 0
    for sample in samples:
        if is_stationary_sample(sample):
            count += 1
        else:
            count = 0
        if count >= min_stationary:
            return True
    return False

