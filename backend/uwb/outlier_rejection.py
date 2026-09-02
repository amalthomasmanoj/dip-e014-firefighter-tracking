from __future__ import annotations


def accept_range(range_m: float, valid: bool, max_range_m: float = 80.0) -> bool:
    return valid and 0.0 <= range_m <= max_range_m

