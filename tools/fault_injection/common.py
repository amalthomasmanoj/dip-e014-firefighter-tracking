from __future__ import annotations

from copy import deepcopy
from typing import Any

PacketRecord = dict[str, Any]


def copy_record(record: PacketRecord) -> PacketRecord:
    return deepcopy(record)


def is_uwb_range_record(record: PacketRecord) -> bool:
    return record.get("type") == "uwb_range"


def timestamp_us(record: PacketRecord) -> int:
    value = record.get("timestamp_us")
    if not isinstance(value, int) or value < 0:
        raise ValueError("record timestamp_us must be a non-negative integer")
    return value


def time_window_us(start_s: float, duration_s: float) -> tuple[int, int]:
    if start_s < 0.0:
        raise ValueError("start_s must be non-negative")
    if duration_s < 0.0:
        raise ValueError("duration_s must be non-negative")
    start_us = round(start_s * 1_000_000)
    return start_us, start_us + round(duration_s * 1_000_000)
