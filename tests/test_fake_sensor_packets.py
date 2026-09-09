from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from tools.fake_data.sensor_packets import (
    simulated_imu_packet_stream,
    simulated_mixed_packet_stream,
    simulated_uwb_range_packet_stream,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET_SCHEMA = json.loads((ROOT / "contracts" / "packet_schema.json").read_text())


def assert_packets_validate(packets: list[dict]) -> None:
    for packet in packets:
        jsonschema.validate(packet, PACKET_SCHEMA)


def assert_monotonic_packet_metadata(packets: list[dict]) -> None:
    sequence_numbers = [packet["sequence_number"] for packet in packets]
    timestamps = [packet["timestamp_us"] for packet in packets]
    assert sequence_numbers == sorted(sequence_numbers)
    assert timestamps == sorted(timestamps)
    assert len(set(sequence_numbers)) == len(sequence_numbers)
    assert len(set(timestamps)) == len(timestamps)


def test_generated_imu_packets_validate_against_contract() -> None:
    packets = list(simulated_imu_packet_stream(packet_count=8))

    assert_packets_validate(packets)
    assert {packet["type"] for packet in packets} == {"imu"}


def test_generated_uwb_packets_validate_against_contract() -> None:
    packets = list(simulated_uwb_range_packet_stream(packet_count=8))

    assert_packets_validate(packets)
    assert {packet["type"] for packet in packets} == {"uwb_range"}
    assert {packet["data"]["quality"] for packet in packets} == {None}


def test_generated_uwb_ranges_use_default_anchors_and_path() -> None:
    packets = list(simulated_uwb_range_packet_stream(packet_count=3))

    assert [packet["data"]["anchor_id"] for packet in packets] == ["A1", "A2", "A3"]
    assert packets[0]["data"]["range_m"] == pytest.approx(2**0.5)
    assert packets[1]["data"]["range_m"] == pytest.approx(
        ((8.0 - 1.08) ** 2 + (0.0 - 1.0) ** 2) ** 0.5
    )
    assert packets[2]["data"]["range_m"] == pytest.approx(
        ((0.0 - 1.16) ** 2 + (6.0 - 1.0) ** 2) ** 0.5
    )


@pytest.mark.parametrize(
    "packets",
    [
        list(simulated_imu_packet_stream(packet_count=8)),
        list(simulated_uwb_range_packet_stream(packet_count=8)),
        list(simulated_mixed_packet_stream(packet_count=8)),
    ],
)
def test_generated_packets_have_monotonic_timestamps_and_sequences(
    packets: list[dict],
) -> None:
    assert_monotonic_packet_metadata(packets)


def test_generated_packets_are_deterministic() -> None:
    assert list(simulated_imu_packet_stream(packet_count=6)) == list(
        simulated_imu_packet_stream(packet_count=6)
    )
    assert list(simulated_uwb_range_packet_stream(packet_count=6)) == list(
        simulated_uwb_range_packet_stream(packet_count=6)
    )
    assert list(simulated_mixed_packet_stream(packet_count=6)) == list(
        simulated_mixed_packet_stream(packet_count=6)
    )


def test_mixed_packets_validate_against_contract() -> None:
    packets = list(simulated_mixed_packet_stream(packet_count=12))

    assert_packets_validate(packets)
    assert {packet["type"] for packet in packets} == {"imu", "uwb_range"}
