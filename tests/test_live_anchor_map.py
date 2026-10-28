from __future__ import annotations

import json

import pytest

from backend.api.app import create_app
from backend.config.source import SourceMode
from backend.ingestion.events import IngestedMeasurement
from backend.ingestion.pipeline import ingest_datagram
from backend.ingestion.sequencing import SequenceStatus, SequenceTracker
from backend.models.measurements import UwbPairRangeMeasurement
from backend.uwb.anchor_map import LiveAnchorMapTracker, solve_three_anchor_map
from backend.uwb.anchors import Anchor
from tools.uwb.dwm3000_udp_adapter import generic_packets_from_sweep, parse_dwm3000_sweep

ANCHORS = (
    Anchor("A1", 0.0, 0.0),
    Anchor("A2", 8.0, 0.0),
    Anchor("A3", 0.0, 6.0),
)


def pair_event(
    first_id: str,
    second_id: str,
    range_m: float,
    sequence_number: int,
    arrival_time_s: float,
    *,
    valid: bool = True,
) -> IngestedMeasurement:
    return IngestedMeasurement(
        measurement=UwbPairRangeMeasurement(
            timestamp_us=sequence_number * 1_000,
            node_id=first_id,
            sequence_number=sequence_number,
            peer_id=second_id,
            range_m=range_m,
            valid=valid,
            rssi_gap_db=5.0,
            rssi_dbm=-78.0,
        ),
        sequence_status=SequenceStatus(
            node_id=first_id,
            sequence_number=sequence_number,
            gap_detected=False,
            out_of_order=False,
            expected_sequence_number=None,
        ),
        arrival_time_s=arrival_time_s,
        raw_payload=b"raw pair result",
    )


def feed_triangle(
    tracker: LiveAnchorMapTracker,
    *,
    start_sequence: int,
    arrival_time_s: float,
    d12: float = 4.0,
    d13: float = 3.0,
    d23: float = 5.0,
) -> bool:
    updated = False
    for offset, (first, second, distance) in enumerate(
        (("A1", "A2", d12), ("A1", "A3", d13), ("A2", "A3", d23))
    ):
        updated = tracker.observe(
            pair_event(
                first,
                second,
                distance,
                start_sequence + offset,
                arrival_time_s + offset * 0.01,
            )
        ) or updated
    return updated


def test_three_anchor_solution_fixes_origin_axis_and_positive_y() -> None:
    solved = solve_three_anchor_map(
        ("A1", "A2", "A3"),
        {("A1", "A2"): 4.0, ("A1", "A3"): 3.0, ("A2", "A3"): 5.0},
    )

    assert solved == (
        Anchor("A1", 0.0, 0.0),
        Anchor("A2", 4.0, 0.0),
        Anchor("A3", 0.0, 3.0),
    )


def test_impossible_triangle_is_rejected() -> None:
    with pytest.raises(ValueError, match="do not form a triangle"):
        solve_three_anchor_map(
            ("A1", "A2", "A3"),
            {("A1", "A2"): 10.0, ("A1", "A3"): 2.0, ("A2", "A3"): 2.0},
        )


def test_tracker_commits_initial_map_after_filtered_complete_sets() -> None:
    tracker = LiveAnchorMapTracker(ANCHORS, minimum_samples_per_pair=3)

    assert not feed_triangle(tracker, start_sequence=1, arrival_time_s=10.0)
    assert not feed_triangle(tracker, start_sequence=4, arrival_time_s=10.2)
    assert feed_triangle(tracker, start_sequence=7, arrival_time_s=10.4)

    snapshot = tracker.snapshot(now_s=10.5)
    assert snapshot["status"] == "ready"
    assert snapshot["map_version"] == 1
    assert tracker.anchors[1].x_m == pytest.approx(4.0)
    assert tracker.anchors[2].x_m == pytest.approx(0.0)
    assert tracker.anchors[2].y_m == pytest.approx(3.0)
    assert len(snapshot["links"]) == 3


def test_tracker_requires_sustained_movement_before_new_map_version() -> None:
    tracker = LiveAnchorMapTracker(
        ANCHORS,
        median_window=3,
        minimum_samples_per_pair=1,
        movement_confirmation_sets=3,
    )
    assert feed_triangle(tracker, start_sequence=1, arrival_time_s=10.0)

    assert not feed_triangle(
        tracker,
        start_sequence=4,
        arrival_time_s=10.2,
        d13=4.0,
        d23=5.657,
    )
    assert tracker.map_version == 1
    assert not feed_triangle(
        tracker,
        start_sequence=7,
        arrival_time_s=10.4,
        d13=4.0,
        d23=5.657,
    )
    assert not feed_triangle(
        tracker,
        start_sequence=10,
        arrival_time_s=10.6,
        d13=4.0,
        d23=5.657,
    )
    assert feed_triangle(
        tracker,
        start_sequence=13,
        arrival_time_s=10.8,
        d13=4.0,
        d23=5.657,
    )
    assert tracker.map_version == 2
    assert tracker.anchors[2].y_m == pytest.approx(4.0, abs=0.02)


def test_invalid_and_stale_results_degrade_without_replacing_last_map() -> None:
    tracker = LiveAnchorMapTracker(ANCHORS, minimum_samples_per_pair=1, stale_after_s=1.0)
    assert feed_triangle(tracker, start_sequence=1, arrival_time_s=10.0)
    original = tracker.anchors

    tracker.observe(pair_event("A1", "A2", 0.0, 4, 10.5, valid=False))
    snapshot = tracker.snapshot(now_s=11.2)

    assert snapshot["status"] == "degraded"
    assert snapshot["map_version"] == 1
    assert tracker.anchors == original
    assert snapshot["last_error"] == "rejected invalid or unsupported pair range"


def test_fewer_than_three_configured_anchors_keep_fixed_bringup_map() -> None:
    configured = ANCHORS[:2]
    tracker = LiveAnchorMapTracker(configured)

    assert not tracker.observe(pair_event("A1", "A2", 4.0, 1, 10.0))
    assert tracker.anchors == configured
    assert tracker.snapshot(now_s=10.1)["status"] == "unavailable"


def test_adapter_to_live_api_commits_surveyed_anchor_coordinates() -> None:
    app = create_app(source_mode=SourceMode.UDP, anchors=ANCHORS)
    sequence_tracker = SequenceTracker()
    sequence_number = 0
    for cycle in range(3):
        sweep = parse_dwm3000_sweep(
            {
                "t": 1_000 + cycle,
                "tag_id": 10,
                "anchors": {},
                "surveys": [
                    {
                        "initiator_id": 1,
                        "target_id": 2,
                        "ok": True,
                        "distance_mm": 4_000,
                        "rssi_gap_db": 5,
                        "rssi_dbm": -78,
                    },
                    {
                        "initiator_id": 1,
                        "target_id": 3,
                        "ok": True,
                        "distance_mm": 3_000,
                        "rssi_gap_db": 5,
                        "rssi_dbm": -78,
                    },
                    {
                        "initiator_id": 2,
                        "target_id": 3,
                        "ok": True,
                        "distance_mm": 5_000,
                        "rssi_gap_db": 5,
                        "rssi_dbm": -78,
                    },
                ],
            }
        )
        packets = generic_packets_from_sweep(sweep, sequence_number)
        sequence_number += len(packets)
        for offset, packet in enumerate(packets):
            event = ingest_datagram(
                json.dumps(packet).encode(),
                sequence_tracker,
                arrival_time_s=10.0 + cycle * 0.1 + offset * 0.01,
            )
            assert app.state.live_hub.process(event) is None

    anchors_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/anchors"
    )
    anchor_map_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/uwb/anchor-map"
    )

    assert anchors_route.endpoint() == [
        {"anchor_id": "A1", "x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
        {"anchor_id": "A2", "x_m": 4.0, "y_m": 0.0, "z_m": 0.0},
        {"anchor_id": "A3", "x_m": 0.0, "y_m": 3.0, "z_m": 0.0},
    ]
    assert anchor_map_route.endpoint()["map_version"] == 1
