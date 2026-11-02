from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean

from backend.config.responders import RotationMatrix
from backend.models.measurements import ImuMeasurement

STANDARD_GRAVITY_MPS2 = 9.80665
MIN_CALIBRATION_SAMPLES = 25
MAX_ACCEL_RMS_DEVIATION_MPS2 = 0.35
MAX_MEAN_GYRO_NORM_RADPS = 0.15


@dataclass(frozen=True)
class MountCalibration:
    sensor_to_body: RotationMatrix
    sample_count: int
    mean_accel_mps2: tuple[float, float, float]
    accel_rms_deviation_mps2: float
    mean_gyro_norm_radps: float


def _rotation_to_body_up(
    sensor_up: tuple[float, float, float],
) -> RotationMatrix:
    """Return the minimal right-handed rotation mapping sensor up to body +Z."""
    ax, ay, az = sensor_up
    # v = sensor_up x body_up, c = sensor_up dot body_up.
    vx, vy, vz = ay, -ax, 0.0
    c = az
    if c >= 1.0 - 1e-9:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if c <= -1.0 + 1e-9:
        # A 180-degree rotation around sensor X maps -Z to body +Z.
        return ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))

    skew = (
        (0.0, -vz, vy),
        (vz, 0.0, -vx),
        (-vy, vx, 0.0),
    )
    skew_squared = tuple(
        tuple(sum(skew[row][axis] * skew[axis][column] for axis in range(3)) for column in range(3))
        for row in range(3)
    )
    scale = 1.0 / (1.0 + c)
    return tuple(
        tuple(
            (1.0 if row == column else 0.0)
            + skew[row][column]
            + skew_squared[row][column] * scale
            for column in range(3)
        )
        for row in range(3)
    )  # type: ignore[return-value]


def calibrate_upright_mount(
    samples: tuple[ImuMeasurement, ...] | list[ImuMeasurement],
) -> MountCalibration:
    """Estimate sensor-to-body rotation while the mounted wearer stands still.

    Upright gravity identifies body +Z. Rotation about +Z remains arbitrary, which
    is acceptable for the current baseline: posture uses body Z, gyro heading uses
    angular velocity about body Z, and world yaw is aligned separately in the UI.
    """
    if len(samples) < MIN_CALIBRATION_SAMPLES:
        raise ValueError(
            f"need at least {MIN_CALIBRATION_SAMPLES} stationary IMU samples; "
            f"received {len(samples)}"
        )

    mean_accel = tuple(
        fmean(getattr(sample, field) for sample in samples)
        for field in ("ax_mps2", "ay_mps2", "az_mps2")
    )
    mean_norm = math.sqrt(sum(value * value for value in mean_accel))
    if abs(mean_norm - STANDARD_GRAVITY_MPS2) > 1.0:
        raise ValueError(
            "upright calibration requires acceleration close to gravity; "
            f"measured {mean_norm:.2f} m/s^2"
        )

    accel_rms = math.sqrt(
        fmean(
            (sample.ax_mps2 - mean_accel[0]) ** 2
            + (sample.ay_mps2 - mean_accel[1]) ** 2
            + (sample.az_mps2 - mean_accel[2]) ** 2
            for sample in samples
        )
    )
    if accel_rms > MAX_ACCEL_RMS_DEVIATION_MPS2:
        raise ValueError(
            "keep the mounted IMU still while calibrating; "
            f"acceleration variation was {accel_rms:.2f} m/s^2"
        )

    mean_gyro_norm = fmean(
        math.sqrt(sample.gx_radps**2 + sample.gy_radps**2 + sample.gz_radps**2)
        for sample in samples
    )
    if mean_gyro_norm > MAX_MEAN_GYRO_NORM_RADPS:
        raise ValueError(
            "keep the mounted IMU still while calibrating; "
            f"angular rate was {mean_gyro_norm:.2f} rad/s"
        )

    sensor_up = tuple(value / mean_norm for value in mean_accel)
    return MountCalibration(
        sensor_to_body=_rotation_to_body_up(sensor_up),  # type: ignore[arg-type]
        sample_count=len(samples),
        mean_accel_mps2=mean_accel,  # type: ignore[arg-type]
        accel_rms_deviation_mps2=accel_rms,
        mean_gyro_norm_radps=mean_gyro_norm,
    )
