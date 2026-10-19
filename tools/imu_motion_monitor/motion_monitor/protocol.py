"""DIP UDP 包的只读解析；不依赖根目录模块。
Read-only parser for DIP UDP packets; no dependency on root modules.
"""
from __future__ import annotations

import math
from typing import Any

IMU_FIELDS = ("ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps")


def parse_imu_packet(packet: Any) -> tuple[int, int, tuple[float, float, float], tuple[float, float, float]] | None:
    """解析一个 IMU 包；字段不全、非有限值或时间戳非法时返回 None。
    Parse one IMU packet; return None for missing fields, non-finite values or invalid timestamps.
    """
    if not isinstance(packet, dict) or packet.get("type") != "imu":
        return None
    timestamp = packet.get("timestamp_us")
    sequence = packet.get("sequence_number")
    if type(timestamp) is not int or timestamp < 0:
        return None
    if type(sequence) is not int or sequence < 0:
        return None
    data = packet.get("data")
    if not isinstance(data, dict):
        return None
    try:
        values = [float(data[key]) for key in IMU_FIELDS]
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    return timestamp, sequence, (values[0], values[1], values[2]), (values[3], values[4], values[5])
