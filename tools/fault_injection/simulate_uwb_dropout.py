from __future__ import annotations

from typing import Literal

from tools.fault_injection.common import (
    PacketRecord,
    copy_record,
    is_uwb_range_record,
    time_window_us,
    timestamp_us,
)

DropoutMode = Literal["drop", "invalidate"]


def simulate_uwb_dropout(
    records: list[PacketRecord],
    start_s: float,
    duration_s: float,
    mode: DropoutMode = "drop",
) -> list[PacketRecord]:
    """Drop or invalidate UWB records whose timestamp falls in a time window.

    The target window is `[start_s, start_s + duration_s)`. `mode="drop"`
    removes matching UWB records. `mode="invalidate"` preserves matching UWB
    records but sets `data.valid` to `False`. Non-UWB records are preserved by
    value.
    """
    if mode not in ("drop", "invalidate"):
        raise ValueError("mode must be 'drop' or 'invalidate'")

    start_us, end_us = time_window_us(start_s=start_s, duration_s=duration_s)
    transformed: list[PacketRecord] = []
    for record in records:
        next_record = copy_record(record)
        in_window = start_us <= timestamp_us(next_record) < end_us
        if is_uwb_range_record(next_record) and in_window:
            if mode == "drop":
                continue
            data = next_record.get("data")
            if not isinstance(data, dict):
                raise ValueError("UWB record data must be an object")
            data["valid"] = False
        transformed.append(next_record)
    return transformed
