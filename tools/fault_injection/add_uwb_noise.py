from __future__ import annotations

import random

from tools.fault_injection.common import PacketRecord, copy_record, is_uwb_range_record


def add_uwb_noise(
    records: list[PacketRecord],
    sigma_m: float,
    seed: int = 0,
) -> list[PacketRecord]:
    """Add deterministic Gaussian noise to UWB range records.

    Expected record shape is a packet-like dictionary with top-level `type` and
    nested `data.range_m`. Non-UWB records are preserved by value. Generated
    negative ranges are clamped to `0.0` to keep packet records contract-valid.
    """
    if sigma_m < 0.0:
        raise ValueError("sigma_m must be non-negative")

    rng = random.Random(seed)
    transformed: list[PacketRecord] = []
    for record in records:
        next_record = copy_record(record)
        if is_uwb_range_record(next_record):
            data = next_record.get("data")
            if not isinstance(data, dict):
                raise ValueError("UWB record data must be an object")
            range_m = data.get("range_m")
            if not isinstance(range_m, int | float) or isinstance(range_m, bool):
                raise ValueError("UWB data.range_m must be numeric")
            data["range_m"] = max(0.0, float(range_m) + rng.gauss(0.0, sigma_m))
        transformed.append(next_record)
    return transformed
