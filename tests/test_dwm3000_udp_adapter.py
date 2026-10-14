from __future__ import annotations

import json

import pytest

from backend.ingestion.parser import parse_packet
from backend.models.measurements import UwbPairRangeMeasurement, UwbRangeMeasurement
from tools.uwb.dwm3000_udp_adapter import (
    generic_packets_from_sweep,
    parse_dwm3000_sweep,
)

LIVE_FORMAT_SAMPLE = {
    "t": 512834,
    "tag_id": 10,
    "anchors": {
        "A1": {
            "distance": 154.36,
            "raw": 154.36,
            "rssi": -78.94,
            "fp_rssi": -101.47,
        },
        "A2": {
            "distance": 195.18,
            "raw": 195.18,
            "rssi": -74.96,
            "fp_rssi": -82.60,
        },
    },
}


def test_live_dwm3000_sweep_converts_to_generic_measurements() -> None:
    sweep = parse_dwm3000_sweep(json.dumps(LIVE_FORMAT_SAMPLE).encode())

    packets = generic_packets_from_sweep(sweep, start_sequence_number=40)
    measurements = [parse_packet(packet) for packet in packets]

    assert len(measurements) == 2
    assert all(isinstance(measurement, UwbRangeMeasurement) for measurement in measurements)
    assert [measurement.anchor_id for measurement in measurements] == ["A1", "A2"]
    assert [measurement.sequence_number for measurement in measurements] == [40, 41]
    assert measurements[0].node_id == "dwm3000_tag_10"
    assert measurements[0].timestamp_us == 512_834_000
    assert measurements[0].range_m == pytest.approx(1.5436)
    assert measurements[0].quality is None


def test_partial_anchor_sweep_is_valid() -> None:
    sample = dict(LIVE_FORMAT_SAMPLE)
    sample["anchors"] = {"A2": LIVE_FORMAT_SAMPLE["anchors"]["A2"]}

    sweep = parse_dwm3000_sweep(sample)
    packets = generic_packets_from_sweep(sweep, start_sequence_number=0)

    assert len(packets) == 1
    assert packets[0]["data"]["anchor_id"] == "A2"


def test_stage_six_survey_result_converts_to_pair_measurement() -> None:
    sample = {
        "t": 512_900,
        "tag_id": 10,
        "anchors": {},
        "surveys": [
            {
                "initiator_id": 1,
                "target_id": 2,
                "ok": True,
                "distance_mm": 1967,
                "rssi_gap_db": 5,
                "rssi_dbm": -78,
            }
        ],
    }

    sweep = parse_dwm3000_sweep(sample)
    packets = generic_packets_from_sweep(sweep, start_sequence_number=50)
    measurement = parse_packet(packets[0])

    assert isinstance(measurement, UwbPairRangeMeasurement)
    assert measurement.node_id == "A1"
    assert measurement.peer_id == "A2"
    assert measurement.range_m == pytest.approx(1.967)
    assert measurement.rssi_gap_db == pytest.approx(5.0)
    assert measurement.rssi_dbm == pytest.approx(-78.0)


def test_sweep_can_carry_tag_ranges_and_survey_results_together() -> None:
    sample = json.loads(json.dumps(LIVE_FORMAT_SAMPLE))
    sample["surveys"] = [
        {
            "initiator_id": 2,
            "target_id": 3,
            "ok": False,
            "distance_mm": 0,
            "rssi_gap_db": None,
            "rssi_dbm": None,
        }
    ]

    packets = generic_packets_from_sweep(
        parse_dwm3000_sweep(sample),
        start_sequence_number=60,
    )

    assert [packet["type"] for packet in packets] == [
        "uwb_range",
        "uwb_range",
        "uwb_pair_range",
    ]
    assert packets[-1]["data"]["valid"] is False


def test_tag_v3_peer_and_legacy_inter_fields_do_not_block_survey_ingestion() -> None:
    sample = json.loads(json.dumps(LIVE_FORMAT_SAMPLE))
    sample.update(
        peer={
            "T11": {"distance": 350.0, "rssi": -70.0, "fp_rssi": -73.0}
        },
        surveys=[
            {
                "initiator_id": 1,
                "target_id": 3,
                "ok": True,
                "distance_mm": 2450,
                "rssi_gap_db": 4,
                "rssi_dbm": -76,
            }
        ],
        inter={"A1-A3": {"distance": 245.0, "gap": 4}},
    )

    packets = generic_packets_from_sweep(parse_dwm3000_sweep(sample), 0)
    pair_measurement = parse_packet(packets[-1])

    assert isinstance(pair_measurement, UwbPairRangeMeasurement)
    assert pair_measurement.node_id == "A1"
    assert pair_measurement.peer_id == "A3"
    assert pair_measurement.range_m == pytest.approx(2.45)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda sample: sample.update(t=-1), "non-negative integer"),
        (lambda sample: sample.update(anchors={}), "anchor range or survey result"),
        (
            lambda sample: sample.update(
                anchors={"anchor-one": LIVE_FORMAT_SAMPLE["anchors"]["A1"]}
            ),
            "invalid anchor ID",
        ),
        (
            lambda sample: sample["anchors"]["A1"].update(distance=-1.0),
            "distances must be non-negative",
        ),
        (
            lambda sample: sample["anchors"]["A1"].update(rssi=float("nan")),
            "must be finite",
        ),
    ],
)
def test_invalid_sweeps_are_rejected(mutation, match: str) -> None:
    sample = json.loads(json.dumps(LIVE_FORMAT_SAMPLE))
    mutation(sample)

    with pytest.raises(ValueError, match=match):
        parse_dwm3000_sweep(sample)


def test_invalid_json_is_reported_as_value_error() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        parse_dwm3000_sweep(b"not-json")


def test_negative_start_sequence_is_rejected() -> None:
    sweep = parse_dwm3000_sweep(LIVE_FORMAT_SAMPLE)

    with pytest.raises(ValueError, match="must be non-negative"):
        generic_packets_from_sweep(sweep, start_sequence_number=-1)
