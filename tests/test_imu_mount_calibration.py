import math

import pytest

from backend.imu.mount_calibration import calibrate_upright_mount
from backend.models.measurements import ImuMeasurement


def samples(
    accel: tuple[float, float, float],
    *,
    count: int = 30,
    gyro: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> list[ImuMeasurement]:
    return [
        ImuMeasurement(
            timestamp_us=index * 20_000,
            node_id="imu_waist_01",
            sequence_number=index,
            ax_mps2=accel[0],
            ay_mps2=accel[1],
            az_mps2=accel[2],
            gx_radps=gyro[0],
            gy_radps=gyro[1],
            gz_radps=gyro[2],
        )
        for index in range(count)
    ]


def rotate(
    matrix: tuple[tuple[float, float, float], ...],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(sum(row[index] * vector[index] for index in range(3)) for row in matrix)


@pytest.mark.parametrize(
    "sensor_accel",
    [
        (9.80665, 0.0, 0.0),
        (0.0, 9.80665, 0.0),
        (0.0, 0.0, 9.80665),
        (0.0, 0.0, -9.80665),
        (6.93435, 0.0, 6.93435),
    ],
)
def test_upright_calibration_maps_mounted_gravity_to_body_up(
    sensor_accel: tuple[float, float, float],
) -> None:
    calibration = calibrate_upright_mount(samples(sensor_accel))

    body_accel = rotate(calibration.sensor_to_body, sensor_accel)
    assert body_accel[0] == pytest.approx(0.0, abs=1e-5)
    assert body_accel[1] == pytest.approx(0.0, abs=1e-5)
    assert body_accel[2] == pytest.approx(math.sqrt(sum(v * v for v in sensor_accel)))


def test_upright_calibration_rejects_too_few_samples() -> None:
    with pytest.raises(ValueError, match="at least 25"):
        calibrate_upright_mount(samples((0.0, 0.0, 9.80665), count=24))


def test_upright_calibration_rejects_motion() -> None:
    moving = samples((0.0, 0.0, 9.80665))
    moving[0] = ImuMeasurement(**{**moving[0].__dict__, "ax_mps2": 3.0})

    with pytest.raises(ValueError, match="keep the mounted IMU still"):
        calibrate_upright_mount(moving)


def test_upright_calibration_rejects_rotation() -> None:
    with pytest.raises(ValueError, match="angular rate"):
        calibrate_upright_mount(
            samples((0.0, 0.0, 9.80665), gyro=(0.0, 0.0, 0.3))
        )
