from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.ingestion.pipeline import ingest_datagram, ingest_datagrams
from backend.ingestion.sequencing import SequenceTracker
from backend.models.measurements import ImuMeasurement, UwbRangeMeasurement

ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return json.loads((ROOT / "contracts" / "examples" / name).read_text())


def encode_packet(packet: dict) -> bytes:
    return json.dumps(packet).encode("utf-8")


def test_valid_imu_udp_payload_becomes_ingested_measurement() -> None:
    payload = encode_packet(load_example("imu_packet.json"))
    tracker = SequenceTracker()

    event = ingest_datagram(payload, tracker, arrival_time_s=42.5)

    assert isinstance(event.measurement, ImuMeasurement)
    assert event.measurement.node_id == "wearable_01"
    assert event.measurement.sequence_number == 1001
    assert not event.sequence_status.gap_detected
    assert not event.sequence_status.out_of_order
    assert event.arrival_time_s == 42.5
    assert event.raw_payload == payload


def test_valid_uwb_udp_payload_becomes_ingested_measurement() -> None:
    payload = encode_packet(load_example("uwb_range_packet.json"))
    tracker = SequenceTracker()

    event = ingest_datagram(payload, tracker, arrival_time_s=43.5)

    assert isinstance(event.measurement, UwbRangeMeasurement)
    assert event.measurement.anchor_id == "A1"
    assert event.measurement.range_m == pytest.approx(4.23)
    assert event.sequence_status.node_id == "wearable_01"
    assert event.sequence_status.sequence_number == 1002


def test_sequence_gap_is_reported_in_metadata() -> None:
    packet = load_example("imu_packet.json")
    tracker = SequenceTracker()

    first = dict(packet, sequence_number=10)
    gap_packet = dict(packet, sequence_number=12)

    ingest_datagram(encode_packet(first), tracker, arrival_time_s=1.0)
    event = ingest_datagram(encode_packet(gap_packet), tracker, arrival_time_s=2.0)

    assert event.sequence_status.gap_detected
    assert not event.sequence_status.out_of_order
    assert event.sequence_status.expected_sequence_number == 11


def test_out_of_order_packet_is_reported_in_metadata() -> None:
    packet = load_example("imu_packet.json")
    tracker = SequenceTracker()

    newer = dict(packet, sequence_number=12)
    older = dict(packet, sequence_number=11)

    ingest_datagram(encode_packet(newer), tracker, arrival_time_s=1.0)
    event = ingest_datagram(encode_packet(older), tracker, arrival_time_s=2.0)

    assert event.sequence_status.out_of_order
    assert not event.sequence_status.gap_detected
    assert event.sequence_status.expected_sequence_number == 13


def test_invalid_packet_is_rejected() -> None:
    packet = load_example("imu_packet.json")
    del packet["timestamp_us"]

    with pytest.raises(ValueError, match="missing required packet fields"):
        ingest_datagram(encode_packet(packet), SequenceTracker(), arrival_time_s=1.0)


def test_original_timestamp_is_preserved_separately_from_arrival_time() -> None:
    packet = load_example("imu_packet.json")
    packet["timestamp_us"] = 123456789
    payload = encode_packet(packet)

    event = ingest_datagram(payload, SequenceTracker(), arrival_time_s=987.654)

    assert event.measurement.timestamp_us == 123456789
    assert event.arrival_time_s == 987.654


async def _payload_stream(payloads: list[bytes]):
    for payload in payloads:
        yield payload


async def _collect(payloads: list[bytes]) -> list:
    return [event async for event in ingest_datagrams(_payload_stream(payloads))]


def test_malformed_datagram_is_skipped_without_ending_the_stream() -> None:
    good = encode_packet(load_example("imu_packet.json"))
    later = encode_packet(dict(load_example("imu_packet.json"), sequence_number=1002))

    events = asyncio.run(_collect([good, b"DIP_PING 69ce316f0dc8a1f2", later]))

    assert [event.measurement.sequence_number for event in events] == [1001, 1002]


def test_unknown_packet_type_is_skipped_without_ending_the_stream() -> None:
    good = encode_packet(load_example("uwb_range_packet.json"))
    unknown = encode_packet(dict(load_example("imu_packet.json"), type="uwb"))

    events = asyncio.run(_collect([unknown, good]))

    assert [event.measurement.anchor_id for event in events] == ["A1"]


def test_non_utf8_datagram_is_skipped_without_ending_the_stream() -> None:
    good = encode_packet(load_example("imu_packet.json"))

    events = asyncio.run(_collect([b"\xff\xfe\x00binary", good]))

    assert len(events) == 1
