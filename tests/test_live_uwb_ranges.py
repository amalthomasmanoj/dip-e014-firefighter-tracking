from __future__ import annotations

import pytest

from backend.api.live import LiveUdpStateHub
from backend.ingestion.events import IngestedMeasurement
from backend.ingestion.sequencing import SequenceStatus
from backend.models.measurements import ImuMeasurement, UwbRangeMeasurement
from backend.uwb.live_ranges import LiveUwbRangeTracker


def sequence_status(sequence_number: int) -> SequenceStatus:
    return SequenceStatus(
        node_id="dwm3000_tag_10",
        sequence_number=sequence_number,
        gap_detected=False,
        out_of_order=False,
        expected_sequence_number=None,
    )


def uwb_event(
    anchor_id: str,
    range_m: float,
    sequence_number: int,
    arrival_time_s: float,
    *,
    valid: bool = True,
) -> IngestedMeasurement:
    return IngestedMeasurement(
        measurement=UwbRangeMeasurement(
            timestamp_us=sequence_number * 1_000,
            node_id="dwm3000_tag_10",
            sequence_number=sequence_number,
            anchor_id=anchor_id,
            range_m=range_m,
            valid=valid,
            quality=None,
        ),
        sequence_status=sequence_status(sequence_number),
        arrival_time_s=arrival_time_s,
        raw_payload=b"raw sweep",
    )


def test_snapshot_reports_only_fresh_ranges_for_latest_tag() -> None:
    tracker = LiveUwbRangeTracker(stale_after_s=1.0)
    tracker.observe(uwb_event("A1", 1.54, 1, 10.0))
    tracker.observe(uwb_event("A2", 1.95, 2, 10.2))

    snapshot = tracker.snapshot(now_s=10.5)

    assert snapshot["tag_present"] is True
    assert snapshot["tag_node_id"] == "dwm3000_tag_10"
    assert snapshot["active_anchor_count"] == 2
    assert [item["anchor_id"] for item in snapshot["ranges"]] == ["A1", "A2"]
    assert snapshot["ranges"][0]["range_m"] == pytest.approx(1.54)
    assert snapshot["ranges"][0]["age_s"] == pytest.approx(0.5)


def test_stale_ranges_disappear_without_overwriting_measurements() -> None:
    tracker = LiveUwbRangeTracker(stale_after_s=1.0)
    event = uwb_event("A1", 1.54, 1, 10.0)
    tracker.observe(event)

    snapshot = tracker.snapshot(now_s=11.1)

    assert snapshot["tag_present"] is False
    assert snapshot["active_anchor_count"] == 0
    assert snapshot["ranges"] == []
    assert event.raw_payload == b"raw sweep"


def test_invalid_range_removes_anchor_and_imu_is_ignored() -> None:
    tracker = LiveUwbRangeTracker(stale_after_s=1.0)
    tracker.observe(uwb_event("A1", 1.54, 1, 10.0))
    tracker.observe(uwb_event("A1", 1.54, 2, 10.1, valid=False))
    tracker.observe(
        IngestedMeasurement(
            measurement=ImuMeasurement(
                timestamp_us=3_000,
                node_id="imu_01",
                sequence_number=3,
                ax_mps2=0.0,
                ay_mps2=0.0,
                az_mps2=9.81,
                gx_radps=0.0,
                gy_radps=0.0,
                gz_radps=0.0,
            ),
            sequence_status=sequence_status(3),
            arrival_time_s=10.2,
            raw_payload=b"imu",
        )
    )

    assert tracker.snapshot(now_s=10.3)["active_anchor_count"] == 0


def test_live_hub_updates_ranges_before_position_is_solvable() -> None:
    tracker = LiveUwbRangeTracker(stale_after_s=1.0)
    hub = LiveUdpStateHub(tracker)

    message = hub.process(uwb_event("A1", 1.54, 1, 10.0))

    assert message is None
    snapshot = tracker.snapshot(now_s=10.1)
    assert snapshot["tag_present"] is True
    assert snapshot["active_anchor_count"] == 1
