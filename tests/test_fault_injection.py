from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from tools.fake_data.sensor_packets import (
    simulated_imu_packet_stream,
    simulated_mixed_packet_stream,
    simulated_uwb_range_packet_stream,
)
from tools.fault_injection.add_uwb_latency import add_uwb_latency
from tools.fault_injection.add_uwb_noise import add_uwb_noise
from tools.fault_injection.simulate_uwb_dropout import simulate_uwb_dropout

ROOT = Path(__file__).resolve().parents[1]
PACKET_SCHEMA = json.loads((ROOT / "contracts" / "packet_schema.json").read_text())


def uwb_records(count: int = 6) -> list[dict]:
    return list(simulated_uwb_range_packet_stream(packet_count=count))


def test_uwb_noise_is_deterministic_with_fixed_seed() -> None:
    records = uwb_records()

    first = add_uwb_noise(records, sigma_m=0.2, seed=123)
    second = add_uwb_noise(records, sigma_m=0.2, seed=123)

    assert first == second
    assert [record["data"]["range_m"] for record in first] != [
        record["data"]["range_m"] for record in records
    ]


def test_uwb_noise_keeps_ranges_non_negative_and_contract_valid() -> None:
    records = uwb_records()

    transformed = add_uwb_noise(records, sigma_m=100.0, seed=0)

    for record in transformed:
        assert record["data"]["range_m"] >= 0.0
        jsonschema.validate(record, PACKET_SCHEMA)


def test_uwb_noise_preserves_non_uwb_records() -> None:
    records = list(simulated_mixed_packet_stream(packet_count=4))

    transformed = add_uwb_noise(records, sigma_m=0.5, seed=0)

    for before, after in zip(records, transformed, strict=True):
        if before["type"] != "uwb_range":
            assert after == before


def test_target_window_dropout_removes_only_matching_uwb_records() -> None:
    records = list(simulated_mixed_packet_stream(packet_count=8))

    transformed = simulate_uwb_dropout(records, start_s=1.3, duration_s=0.2)

    assert [record["sequence_number"] for record in transformed] == [
        1001,
        1002,
        1003,
        1005,
        1006,
        1007,
        1008,
    ]
    assert all(record["sequence_number"] != 1004 for record in transformed)


def test_dropout_does_not_remove_non_uwb_records_in_target_window() -> None:
    records = list(simulated_imu_packet_stream(packet_count=4))

    transformed = simulate_uwb_dropout(records, start_s=1.0, duration_s=0.4)

    assert transformed == records


def test_target_window_dropout_can_invalidate_matching_uwb_records() -> None:
    records = list(simulated_mixed_packet_stream(packet_count=8))

    transformed = simulate_uwb_dropout(
        records,
        start_s=1.3,
        duration_s=0.2,
        mode="invalidate",
    )

    invalidated = [record for record in transformed if record["sequence_number"] == 1004]
    assert len(invalidated) == 1
    assert invalidated[0]["type"] == "uwb_range"
    assert invalidated[0]["data"]["valid"] is False
    assert len(transformed) == len(records)
    for record in transformed:
        jsonschema.validate(record, PACKET_SCHEMA)


def test_uwb_latency_preserves_timestamp_and_adds_arrival_metadata() -> None:
    records = uwb_records(count=1)
    original_timestamp_us = records[0]["timestamp_us"]

    transformed = add_uwb_latency(records, latency_s=0.25)

    assert transformed[0]["timestamp_us"] == original_timestamp_us
    assert transformed[0]["arrival_delay_us"] == 250_000
    assert transformed[0]["arrival_time_us"] == original_timestamp_us + 250_000


def test_uwb_latency_preserves_non_uwb_records() -> None:
    records = list(simulated_mixed_packet_stream(packet_count=4))

    transformed = add_uwb_latency(records, latency_s=0.25)

    for before, after in zip(records, transformed, strict=True):
        if before["type"] != "uwb_range":
            assert after == before
            assert "arrival_time_us" not in after
            assert "arrival_delay_us" not in after
