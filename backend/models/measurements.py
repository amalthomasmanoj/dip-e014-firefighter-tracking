from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Literal


PacketType = Literal["imu", "uwb_range"]


@dataclass(frozen=True)
class ImuMeasurement:
    timestamp_us: int
    node_id: str
    sequence_number: int
    ax_mps2: float
    ay_mps2: float
    az_mps2: float
    gx_radps: float
    gy_radps: float
    gz_radps: float


@dataclass(frozen=True)
class UwbRangeMeasurement:
    timestamp_us: int
    node_id: str
    sequence_number: int
    anchor_id: str
    range_m: float
    valid: bool
    quality: float | None


Measurement = ImuMeasurement | UwbRangeMeasurement


def _require_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"field {key!r} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"field {key!r} must be finite")
    return value


def _require_non_negative_number(data: dict[str, Any], key: str) -> float:
    value = _require_number(data, key)
    if value < 0.0:
        raise ValueError(f"field {key!r} must be non-negative")
    return value


def measurement_from_packet(packet: dict[str, Any]) -> Measurement:
    packet_type = packet.get("type")
    data = packet.get("data")
    if not isinstance(data, dict):
        raise ValueError("packet data must be an object")

    base = {
        "timestamp_us": int(packet["timestamp_us"]),
        "node_id": str(packet["node_id"]),
        "sequence_number": int(packet["sequence_number"]),
    }

    if packet_type == "imu":
        return ImuMeasurement(
            **base,
            ax_mps2=_require_number(data, "ax_mps2"),
            ay_mps2=_require_number(data, "ay_mps2"),
            az_mps2=_require_number(data, "az_mps2"),
            gx_radps=_require_number(data, "gx_radps"),
            gy_radps=_require_number(data, "gy_radps"),
            gz_radps=_require_number(data, "gz_radps"),
        )

    if packet_type == "uwb_range":
        anchor_id = data.get("anchor_id")
        valid = data.get("valid")
        quality = data.get("quality")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise ValueError("anchor_id must be a non-empty string")
        if not isinstance(valid, bool):
            raise ValueError("valid must be a boolean")
        if quality is not None and (
            not isinstance(quality, int | float) or isinstance(quality, bool)
        ):
            raise ValueError("quality must be numeric or null")
        if quality is not None and not math.isfinite(float(quality)):
            raise ValueError("quality must be finite or null")
        return UwbRangeMeasurement(
            **base,
            anchor_id=anchor_id,
            range_m=_require_non_negative_number(data, "range_m"),
            valid=valid,
            quality=None if quality is None else float(quality),
        )

    raise ValueError(f"unsupported packet type {packet_type!r}")
