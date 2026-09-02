from __future__ import annotations

import json
from typing import Any

from backend.models.measurements import Measurement, measurement_from_packet


REQUIRED_PACKET_FIELDS = {
    "version",
    "node_id",
    "sequence_number",
    "timestamp_us",
    "type",
    "data",
}


def parse_packet(payload: str | bytes | dict[str, Any]) -> Measurement:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        packet = json.loads(payload)
    else:
        packet = payload

    if not isinstance(packet, dict):
        raise ValueError("packet must be a JSON object")

    missing = REQUIRED_PACKET_FIELDS - packet.keys()
    if missing:
        raise ValueError(f"missing required packet fields: {sorted(missing)}")

    if packet["version"] != 1:
        raise ValueError("unsupported packet version")
    if not isinstance(packet["node_id"], str) or not packet["node_id"]:
        raise ValueError("node_id must be a non-empty string")
    if not isinstance(packet["sequence_number"], int) or packet["sequence_number"] < 0:
        raise ValueError("sequence_number must be a non-negative integer")
    if not isinstance(packet["timestamp_us"], int) or packet["timestamp_us"] < 0:
        raise ValueError("timestamp_us must be a non-negative integer")

    return measurement_from_packet(packet)

