from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.ingestion.parser import parse_packet
from backend.ingestion.sequencing import SequenceTracker
from backend.models.measurements import ImuMeasurement, UwbRangeMeasurement


ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return json.loads((ROOT / "contracts" / "examples" / name).read_text())


def test_valid_imu_packet_parses() -> None:
    measurement = parse_packet(load_example("imu_packet.json"))
    assert isinstance(measurement, ImuMeasurement)
    assert measurement.ax_mps2 == pytest.approx(0.12)
    assert measurement.gz_radps == pytest.approx(0.1)


def test_valid_uwb_packet_parses() -> None:
    measurement = parse_packet(load_example("uwb_range_packet.json"))
    assert isinstance(measurement, UwbRangeMeasurement)
    assert measurement.anchor_id == "A1"
    assert measurement.quality is None


def test_invalid_packet_rejected() -> None:
    packet = load_example("imu_packet.json")
    packet["version"] = 99
    with pytest.raises(ValueError, match="unsupported packet version"):
        parse_packet(packet)


def test_missing_fields_rejected() -> None:
    packet = load_example("imu_packet.json")
    del packet["timestamp_us"]
    with pytest.raises(ValueError, match="missing required packet fields"):
        parse_packet(packet)


def test_unit_field_names_are_required() -> None:
    packet = load_example("imu_packet.json")
    packet["data"]["ax"] = packet["data"].pop("ax_mps2")
    with pytest.raises(ValueError, match="ax_mps2"):
        parse_packet(packet)


def test_negative_uwb_range_rejected() -> None:
    packet = load_example("uwb_range_packet.json")
    packet["data"]["range_m"] = -4.2
    with pytest.raises(ValueError, match="range_m"):
        parse_packet(packet)


def test_non_finite_values_rejected() -> None:
    packet = load_example("imu_packet.json")
    packet["data"]["ax_mps2"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        parse_packet(packet)


def test_non_finite_quality_rejected() -> None:
    packet = load_example("uwb_range_packet.json")
    packet["data"]["quality"] = float("inf")
    with pytest.raises(ValueError, match="quality"):
        parse_packet(packet)


def test_sequence_gap_and_out_of_order_detected() -> None:
    tracker = SequenceTracker()
    assert not tracker.observe("wearable_01", 10).gap_detected
    gap = tracker.observe("wearable_01", 12)
    assert gap.gap_detected
    assert gap.expected_sequence_number == 11
    old = tracker.observe("wearable_01", 11)
    assert old.out_of_order
