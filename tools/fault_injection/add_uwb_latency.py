from __future__ import annotations


def add_uwb_latency(records: list[dict], latency_s: float) -> list[dict]:
    """Future transform must preserve original measurement timestamp and add arrival time."""
    raise NotImplementedError("UWB latency injection is future work.")

