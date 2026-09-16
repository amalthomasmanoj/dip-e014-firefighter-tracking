from __future__ import annotations

from backend.imu.activity import classify_activity
from backend.models.measurements import ImuMeasurement


def imu_sample(
    ax_mps2: float,
    ay_mps2: float,
    az_mps2: float,
) -> ImuMeasurement:
    return ImuMeasurement(
        timestamp_us=1,
        node_id="wearable_01",
        sequence_number=1,
        ax_mps2=ax_mps2,
        ay_mps2=ay_mps2,
        az_mps2=az_mps2,
        gx_radps=0.0,
        gy_radps=0.0,
        gz_radps=0.0,
    )


def test_classifier_reports_standing_walking_from_upright_motion() -> None:
    activity = classify_activity(
        imu_sample(ax_mps2=0.0, ay_mps2=0.0, az_mps2=9.81),
        speed_mps=0.8,
        zupt_active=False,
    )

    assert activity.posture == "standing"
    assert activity.motion == "walking"
    assert activity.confidence > 0.5


def test_classifier_reports_crouching_walking_from_tilted_motion() -> None:
    activity = classify_activity(
        imu_sample(ax_mps2=7.0, ay_mps2=0.0, az_mps2=7.0),
        speed_mps=0.5,
        zupt_active=False,
    )

    assert activity.posture == "crouching"
    assert activity.motion == "walking"


def test_classifier_reports_stationary_when_zupt_is_active() -> None:
    activity = classify_activity(
        imu_sample(ax_mps2=0.0, ay_mps2=0.0, az_mps2=9.81),
        speed_mps=0.8,
        zupt_active=True,
    )

    assert activity.motion == "stationary"
