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


def test_classifier_does_not_emit_crouching_from_waist_tilt() -> None:
    activity = classify_activity(
        imu_sample(ax_mps2=7.0, ay_mps2=0.0, az_mps2=7.0),
        speed_mps=0.5,
        zupt_active=False,
    )

    assert activity.posture == "standing"
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


def test_classifier_separates_bending_from_lying_down() -> None:
    bending = classify_activity(
        imu_sample(ax_mps2=7.0, ay_mps2=0.0, az_mps2=7.0),
        speed_mps=0.0,
        zupt_active=True,
    )
    prone = classify_activity(
        imu_sample(ax_mps2=9.7, ay_mps2=0.0, az_mps2=-1.0),
        speed_mps=0.0,
        zupt_active=True,
    )

    assert bending.posture == "standing"
    assert prone.posture == "lying_down"


def test_classifier_rejects_invalid_lying_threshold() -> None:
    with pytest.raises(ValueError):
        classify_activity(
            imu_sample(ax_mps2=0.0, ay_mps2=0.0, az_mps2=9.81),
            speed_mps=0.0,
            zupt_active=True,
            lying_tilt_threshold_rad=-0.5,
        )


def test_tilt_classifier_requires_sustained_lying_posture() -> None:
    classifier = TiltActivityClassifier(
        dwell_us=2_000_000,
        max_sample_gap_us=1_100_000,
        low_pass_alpha=1.0,
    )
    sample = imu_sample(ax_mps2=9.81, ay_mps2=0.0, az_mps2=0.0)

    assert classifier.classify(sample, 0.0, False).posture == "standing"
    halfway = ImuMeasurement(**{**sample.__dict__, "timestamp_us": 1_000_001})
    assert classifier.classify(halfway, 0.0, False).posture == "standing"
    sustained = ImuMeasurement(**{**sample.__dict__, "timestamp_us": 2_000_001})
    assert classifier.classify(sustained, 0.0, False).posture == "lying_down"


def test_tilt_classifier_honours_custom_thresholds() -> None:
    sample = imu_sample(ax_mps2=7.0, ay_mps2=0.0, az_mps2=7.0)
    strict = TiltActivityClassifier(
        lying_tilt_threshold_rad=0.7,
        upright_tilt_threshold_rad=0.5,
        dwell_us=0,
        low_pass_alpha=1.0,
    )

    strict.classify(sample, speed_mps=0.0, zupt_active=True)
    next_sample = ImuMeasurement(**{**sample.__dict__, "timestamp_us": 2})
    assert strict.classify(next_sample, speed_mps=0.0, zupt_active=True).posture == "lying_down"
