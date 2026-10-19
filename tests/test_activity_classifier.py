from __future__ import annotations

import pytest

from backend.imu.activity import TiltActivityClassifier, classify_activity
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


def test_classifier_reports_lying_down_when_body_is_horizontal() -> None:
    activity = classify_activity(
        imu_sample(ax_mps2=9.81, ay_mps2=0.0, az_mps2=0.0),
        speed_mps=0.0,
        zupt_active=True,
    )

    assert activity.posture == "lying_down"
    assert activity.motion == "stationary"


def test_classifier_separates_crouching_from_lying_down() -> None:
    crouch = classify_activity(
        imu_sample(ax_mps2=7.0, ay_mps2=0.0, az_mps2=7.0),
        speed_mps=0.0,
        zupt_active=True,
    )
    prone = classify_activity(
        imu_sample(ax_mps2=9.7, ay_mps2=0.0, az_mps2=-1.0),
        speed_mps=0.0,
        zupt_active=True,
    )

    assert crouch.posture == "crouching"
    assert prone.posture == "lying_down"


def test_classifier_rejects_lying_threshold_below_crouch_threshold() -> None:
    with pytest.raises(ValueError):
        classify_activity(
            imu_sample(ax_mps2=0.0, ay_mps2=0.0, az_mps2=9.81),
            speed_mps=0.0,
            zupt_active=True,
            crouch_tilt_threshold_rad=1.0,
            lying_tilt_threshold_rad=0.5,
        )


def test_tilt_classifier_object_matches_function_defaults() -> None:
    sample = imu_sample(ax_mps2=9.81, ay_mps2=0.0, az_mps2=0.0)
    classifier = TiltActivityClassifier()

    assert classifier.classify(sample, speed_mps=0.0, zupt_active=True) == classify_activity(
        sample,
        speed_mps=0.0,
        zupt_active=True,
    )


def test_tilt_classifier_honours_custom_thresholds() -> None:
    sample = imu_sample(ax_mps2=7.0, ay_mps2=0.0, az_mps2=7.0)
    strict = TiltActivityClassifier(lying_tilt_threshold_rad=0.7)

    assert strict.classify(sample, speed_mps=0.0, zupt_active=True).posture == "lying_down"
