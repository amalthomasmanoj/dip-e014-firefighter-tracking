from __future__ import annotations

from tools.fault_injection.common import (
    PacketRecord,
    copy_record,
    is_uwb_range_record,
    timestamp_us,
)


def add_uwb_latency(records: list[PacketRecord], latency_s: float) -> list[PacketRecord]:
    """Add delivery metadata to UWB records without changing measurement time.

    Expected record shape is a packet-like dictionary with top-level
    `timestamp_us`. Only UWB records receive `arrival_delay_us` and
    `arrival_time_us`. Non-UWB records are preserved by value.
    """
    if latency_s < 0.0:
        raise ValueError("latency_s must be non-negative")

    delay_us = round(latency_s * 1_000_000)
    transformed: list[PacketRecord] = []
    for record in records:
        next_record = copy_record(record)
        if is_uwb_range_record(next_record):
            measurement_time_us = timestamp_us(next_record)
            next_record["arrival_delay_us"] = delay_us
            next_record["arrival_time_us"] = measurement_time_us + delay_us
        transformed.append(next_record)
    return transformed
