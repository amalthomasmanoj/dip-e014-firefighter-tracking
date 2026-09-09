from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from typing import Any, Literal

from backend.uwb.anchors import DEFAULT_ANCHORS, Anchor

PacketKind = Literal["imu", "uwb", "mixed"]
SensorPacket = dict[str, Any]

DEFAULT_NODE_ID = "wearable_01"
DEFAULT_START_SEQUENCE = 1001
DEFAULT_START_US = 1_000_000
DEFAULT_DT_S = 0.1


def _path_pose(index: int, dt_s: float) -> tuple[float, float, float, float, float, bool]:
    t = index * dt_s
    if t < 3.0:
        return 1.0 + 0.8 * t, 1.0, 0.8, 0.0, 0.0, False
    if t < 6.0:
        return 3.4, 1.0 + 0.7 * (t - 3.0), 0.0, 0.7, math.pi / 2.0, False
    return 3.4, 3.1, 0.0, 0.0, math.pi / 2.0, True


def path_pose(
    index: int,
    dt_s: float = DEFAULT_DT_S,
) -> tuple[float, float, float, float, float, bool]:
    return _path_pose(index=index, dt_s=dt_s)


def timestamp_for_index(
    index: int,
    start_us: int = DEFAULT_START_US,
    dt_s: float = DEFAULT_DT_S,
) -> int:
    return start_us + int(index * dt_s * 1_000_000)


def _base_packet(
    packet_type: str,
    index: int,
    node_id: str,
    start_sequence: int,
    start_us: int,
    dt_s: float,
) -> SensorPacket:
    return {
        "version": 1,
        "node_id": node_id,
        "sequence_number": start_sequence + index,
        "timestamp_us": timestamp_for_index(index=index, start_us=start_us, dt_s=dt_s),
        "type": packet_type,
    }


def _imu_data(index: int, dt_s: float) -> dict[str, float]:
    _x, _y, vx, vy, _yaw, stopped = _path_pose(index=index, dt_s=dt_s)
    t = index * dt_s
    turning = 3.0 <= t < 3.5

    if stopped:
        ax_mps2 = 0.0
        ay_mps2 = 0.0
        gz_radps = 0.0
    elif turning:
        ax_mps2 = -0.04
        ay_mps2 = 0.04
        gz_radps = math.pi
    else:
        ax_mps2 = 0.02 if vx else 0.0
        ay_mps2 = 0.02 if vy else 0.0
        gz_radps = 0.0

    return {
        "ax_mps2": ax_mps2,
        "ay_mps2": ay_mps2,
        "az_mps2": 9.81,
        "gx_radps": 0.0,
        "gy_radps": 0.0,
        "gz_radps": gz_radps,
    }


def _imu_packet(
    index: int,
    dt_s: float,
    node_id: str,
    start_sequence: int,
    start_us: int,
) -> SensorPacket:
    packet = _base_packet(
        packet_type="imu",
        index=index,
        node_id=node_id,
        start_sequence=start_sequence,
        start_us=start_us,
        dt_s=dt_s,
    )
    packet["data"] = _imu_data(index=index, dt_s=dt_s)
    return packet


def simulated_imu_packet_stream(
    packet_count: int = 90,
    dt_s: float = DEFAULT_DT_S,
    node_id: str = DEFAULT_NODE_ID,
    start_sequence: int = DEFAULT_START_SEQUENCE,
    start_us: int = DEFAULT_START_US,
) -> Iterator[SensorPacket]:
    for index in range(packet_count):
        yield _imu_packet(
            index=index,
            dt_s=dt_s,
            node_id=node_id,
            start_sequence=start_sequence,
            start_us=start_us,
        )


def _range_m(anchor: Anchor, x_m: float, y_m: float, z_m: float = 0.0) -> float:
    return math.sqrt(
        (anchor.x_m - x_m) ** 2
        + (anchor.y_m - y_m) ** 2
        + (anchor.z_m - z_m) ** 2
    )


def _uwb_range_packet(
    index: int,
    anchor: Anchor,
    dt_s: float,
    node_id: str,
    start_sequence: int,
    start_us: int,
) -> SensorPacket:
    x_m, y_m, _vx, _vy, _yaw, _stopped = _path_pose(index=index, dt_s=dt_s)
    packet = _base_packet(
        packet_type="uwb_range",
        index=index,
        node_id=node_id,
        start_sequence=start_sequence,
        start_us=start_us,
        dt_s=dt_s,
    )
    packet["data"] = {
        "anchor_id": anchor.anchor_id,
        "range_m": _range_m(anchor, x_m=x_m, y_m=y_m),
        "valid": True,
        "quality": None,
    }
    return packet


def simulated_uwb_range_packet_stream(
    packet_count: int = 90,
    dt_s: float = DEFAULT_DT_S,
    node_id: str = DEFAULT_NODE_ID,
    start_sequence: int = DEFAULT_START_SEQUENCE,
    start_us: int = DEFAULT_START_US,
    anchors: Sequence[Anchor] = DEFAULT_ANCHORS,
) -> Iterator[SensorPacket]:
    if not anchors:
        raise ValueError("at least one anchor is required")

    for index in range(packet_count):
        anchor = anchors[index % len(anchors)]
        yield _uwb_range_packet(
            index=index,
            anchor=anchor,
            dt_s=dt_s,
            node_id=node_id,
            start_sequence=start_sequence,
            start_us=start_us,
        )


def simulated_mixed_packet_stream(
    packet_count: int = 90,
    dt_s: float = DEFAULT_DT_S,
    node_id: str = DEFAULT_NODE_ID,
    start_sequence: int = DEFAULT_START_SEQUENCE,
    start_us: int = DEFAULT_START_US,
    anchors: Sequence[Anchor] = DEFAULT_ANCHORS,
) -> Iterator[SensorPacket]:
    if not anchors:
        raise ValueError("at least one anchor is required")

    for index in range(packet_count):
        if index % 4 == 3:
            yield _uwb_range_packet(
                index=index,
                anchor=anchors[(index // 4) % len(anchors)],
                dt_s=dt_s,
                node_id=node_id,
                start_sequence=start_sequence,
                start_us=start_us,
            )
        else:
            yield _imu_packet(
                index=index,
                dt_s=dt_s,
                node_id=node_id,
                start_sequence=start_sequence,
                start_us=start_us,
            )
