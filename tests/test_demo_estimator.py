from __future__ import annotations

import pytest

from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.models.measurements import ImuMeasurement, UwbRangeMeasurement
from backend.uwb.anchors import Anchor
from backend.uwb.trilateration import distance_2d


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


def test_estimator_uses_any_three_or_more_configured_anchor_ids() -> None:
    anchors = (
        Anchor("A1", 0.0, 0.0),
        Anchor("A2", 4.0, 0.0),
        Anchor("A4", 0.0, 3.0),
        Anchor("A7", 4.0, 3.0),
    )
    tag = (1.0, 1.0)
    estimator = DemoSensorEstimator(anchors=anchors)
    state = None

    for sequence_number, anchor in enumerate(anchors, start=1):
        state = estimator.update(
            UwbRangeMeasurement(
                timestamp_us=100_000,
                node_id="tag_1",
                sequence_number=sequence_number,
                anchor_id=anchor.anchor_id,
                range_m=distance_2d(anchor, tag),
                valid=True,
                quality=None,
            )
        )

    assert state is not None
    assert state.position_m.x == pytest.approx(1.0)
    assert state.position_m.y == pytest.approx(1.0)
    assert state.status.active_anchor_count == 4


def test_estimator_does_not_count_unconfigured_anchor_as_usable() -> None:
    estimator = DemoSensorEstimator()
    state = None

    for sequence_number, anchor_id in enumerate(("A1", "A2", "A4"), start=1):
        state = estimator.update(
            UwbRangeMeasurement(
                timestamp_us=100_000,
                node_id="tag_1",
                sequence_number=sequence_number,
                anchor_id=anchor_id,
                range_m=2.0,
                valid=True,
                quality=None,
            )
        )

    assert state is None


def test_estimator_waits_for_a_synchronized_range_sweep() -> None:
    anchors = (
        Anchor("A1", 0.0, 0.0),
        Anchor("A2", 4.0, 0.0),
        Anchor("A3", 0.0, 3.0),
    )
    estimator = DemoSensorEstimator(anchors=anchors, range_sync_tolerance_us=1_000)

    for sequence_number, anchor in enumerate(anchors, start=1):
        state = estimator.update(
            UwbRangeMeasurement(
                timestamp_us=100_000,
                node_id="tag_1",
                sequence_number=sequence_number,
                anchor_id=anchor.anchor_id,
                range_m=distance_2d(anchor, (1.0, 1.0)),
                valid=True,
                quality=None,
            )
        )

    assert state is not None
    mixed_sweep_state = estimator.update(
        UwbRangeMeasurement(
            timestamp_us=200_000,
            node_id="tag_1",
            sequence_number=4,
            anchor_id="A1",
            range_m=distance_2d(anchors[0], (2.0, 1.0)),
            valid=True,
            quality=None,
        )
    )

    assert mixed_sweep_state is None
