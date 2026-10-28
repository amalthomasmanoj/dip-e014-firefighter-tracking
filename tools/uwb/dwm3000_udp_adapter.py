from __future__ import annotations

import argparse
import json
import math
import re
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 7007
DEFAULT_TARGET_HOST = "127.0.0.1"
DEFAULT_TARGET_PORT = 9000
ANCHOR_ID_PATTERN = re.compile(r"A[1-9][0-9]*")


class Dwm3000SweepError(ValueError):
    """Raised when a DWM3000 datagram does not match the working wire format."""


@dataclass(frozen=True)
class Dwm3000AnchorSample:
    anchor_id: str
    distance_cm: float
    raw_cm: float
    rssi_dbm: float | None
    fp_rssi_dbm: float | None


@dataclass(frozen=True)
class Dwm3000SurveyResult:
    initiator_id: str
    target_id: str
    valid: bool
    distance_mm: int
    rssi_gap_db: float | None
    rssi_dbm: float | None


@dataclass(frozen=True)
class Dwm3000Sweep:
    timestamp_ms: int
    tag_id: int
    anchors: tuple[Dwm3000AnchorSample, ...]
    surveys: tuple[Dwm3000SurveyResult, ...] = ()
    synthetic: bool = False


def _require_non_negative_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Dwm3000SweepError(f"field {key!r} must be a non-negative integer")
    return value


def _require_finite_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise Dwm3000SweepError(f"field {key!r} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise Dwm3000SweepError(f"field {key!r} must be finite")
    return result


def _optional_finite_number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    return _require_finite_number(data, key)


def _anchor_id_from_number(data: dict[str, Any], key: str) -> str:
    value = _require_non_negative_int(data, key)
    if value == 0:
        raise Dwm3000SweepError(f"field {key!r} must be a positive anchor ID")
    return f"A{value}"


def parse_dwm3000_sweep(payload: bytes | str | dict[str, Any]) -> Dwm3000Sweep:
    """Parse one current-firmware DWM3000 sweep without changing its units."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Dwm3000SweepError("DWM3000 payload must be UTF-8") from exc
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise Dwm3000SweepError("DWM3000 payload must be valid JSON") from exc
    else:
        decoded = payload

    if not isinstance(decoded, dict):
        raise Dwm3000SweepError("DWM3000 sweep must be a JSON object")

    timestamp_ms = _require_non_negative_int(decoded, "t")
    tag_id = _require_non_negative_int(decoded, "tag_id")
    synthetic = decoded.get("synthetic", False)
    if not isinstance(synthetic, bool):
        raise Dwm3000SweepError("field 'synthetic' must be boolean when present")
    anchors = decoded.get("anchors")
    if not isinstance(anchors, dict):
        raise Dwm3000SweepError("field 'anchors' must be an object")

    samples: list[Dwm3000AnchorSample] = []
    for anchor_id, raw_sample in anchors.items():
        if not isinstance(anchor_id, str) or ANCHOR_ID_PATTERN.fullmatch(anchor_id) is None:
            raise Dwm3000SweepError(f"invalid anchor ID {anchor_id!r}")
        if not isinstance(raw_sample, dict):
            raise Dwm3000SweepError(f"anchor {anchor_id!r} data must be an object")

        distance_cm = _require_finite_number(raw_sample, "distance")
        raw_cm = _require_finite_number(raw_sample, "raw")
        if distance_cm < 0.0 or raw_cm < 0.0:
            raise Dwm3000SweepError(
                f"anchor {anchor_id!r} distances must be non-negative"
            )

        samples.append(
            Dwm3000AnchorSample(
                anchor_id=anchor_id,
                distance_cm=distance_cm,
                raw_cm=raw_cm,
                rssi_dbm=_optional_finite_number(raw_sample, "rssi"),
                fp_rssi_dbm=_optional_finite_number(raw_sample, "fp_rssi"),
            )
        )

    raw_surveys = decoded.get("surveys", [])
    if not isinstance(raw_surveys, list):
        raise Dwm3000SweepError("field 'surveys' must be an array")
    surveys: list[Dwm3000SurveyResult] = []
    for index, raw_survey in enumerate(raw_surveys):
        if not isinstance(raw_survey, dict):
            raise Dwm3000SweepError(f"survey {index} must be an object")
        valid = raw_survey.get("ok")
        if not isinstance(valid, bool):
            raise Dwm3000SweepError(f"survey {index} field 'ok' must be boolean")
        distance_mm = _require_non_negative_int(raw_survey, "distance_mm")
        if distance_mm > 65_535:
            raise Dwm3000SweepError("field 'distance_mm' exceeds the stage-6 uint16")
        initiator_id = _anchor_id_from_number(raw_survey, "initiator_id")
        target_id = _anchor_id_from_number(raw_survey, "target_id")
        if initiator_id == target_id:
            raise Dwm3000SweepError("survey anchor IDs must be different")
        surveys.append(
            Dwm3000SurveyResult(
                initiator_id=initiator_id,
                target_id=target_id,
                valid=valid,
                distance_mm=distance_mm,
                rssi_gap_db=_optional_finite_number(raw_survey, "rssi_gap_db"),
                rssi_dbm=_optional_finite_number(raw_survey, "rssi_dbm"),
            )
        )

    if not samples and not surveys:
        raise Dwm3000SweepError("datagram must contain an anchor range or survey result")

    return Dwm3000Sweep(
        timestamp_ms=timestamp_ms,
        tag_id=tag_id,
        anchors=tuple(samples),
        surveys=tuple(surveys),
        synthetic=synthetic,
    )


def generic_packets_from_sweep(
    sweep: Dwm3000Sweep,
    start_sequence_number: int,
) -> list[dict[str, Any]]:
    """Expand a sweep into generic per-anchor packets accepted by the backend."""
    if start_sequence_number < 0:
        raise Dwm3000SweepError("start_sequence_number must be non-negative")

    packets: list[dict[str, Any]] = []
    for offset, sample in enumerate(sweep.anchors):
        packets.append(
            {
                "version": 1,
                "node_id": (
                    f"dwm3000_sim_tag_{sweep.tag_id}"
                    if sweep.synthetic
                    else f"dwm3000_tag_{sweep.tag_id}"
                ),
                "sequence_number": start_sequence_number + offset,
                "timestamp_us": sweep.timestamp_ms * 1_000,
                "type": "uwb_range",
                "data": {
                    "anchor_id": sample.anchor_id,
                    "range_m": sample.distance_cm / 100.0,
                    "valid": True,
                    "quality": None,
                },
            }
        )
    sequence_offset = len(packets)
    for offset, survey in enumerate(sweep.surveys):
        packets.append(
            {
                "version": 1,
                "node_id": survey.initiator_id,
                "sequence_number": start_sequence_number + sequence_offset + offset,
                "timestamp_us": sweep.timestamp_ms * 1_000,
                "type": "uwb_pair_range",
                "data": {
                    "peer_id": survey.target_id,
                    "range_m": survey.distance_mm / 1_000.0,
                    "valid": survey.valid,
                    "rssi_gap_db": survey.rssi_gap_db,
                    "rssi_dbm": survey.rssi_dbm,
                },
            }
        )
    return packets


def _write_raw_record(
    output: TextIO,
    payload: bytes,
    sender: tuple[str, int],
    arrival_time_us: int,
) -> None:
    record = {
        "arrival_time_us": arrival_time_us,
        "sender_ip": sender[0],
        "sender_port": sender[1],
        "payload_utf8": payload.decode("utf-8", errors="replace"),
    }
    output.write(json.dumps(record, separators=(",", ":")) + "\n")
    output.flush()


def run_adapter(
    *,
    listen_host: str,
    listen_port: int,
    target_host: str,
    target_port: int,
    raw_jsonl: Path | None,
) -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver.bind((listen_host, listen_port))
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    raw_output: TextIO | None = None
    sequence_numbers_by_node: dict[str, int] = {}
    sweeps_received = 0
    packets_forwarded = 0
    surveys_received = 0
    parse_errors = 0
    anchors_seen: set[str] = set()

    if raw_jsonl is not None:
        raw_output = raw_jsonl.open("a", encoding="utf-8")

    print(
        f"Listening for DWM3000 sweeps on {listen_host}:{listen_port}; "
        f"forwarding generic packets to {target_host}:{target_port}"
    )
    try:
        while True:
            payload, source = receiver.recvfrom(65_535)
            arrival_time_us = time.time_ns() // 1_000
            if raw_output is not None:
                _write_raw_record(raw_output, payload, source, arrival_time_us)

            try:
                sweep = parse_dwm3000_sweep(payload)
            except Dwm3000SweepError as exc:
                parse_errors += 1
                print(f"Rejected DWM3000 datagram from {source[0]}:{source[1]}: {exc}")
                continue

            packets = generic_packets_from_sweep(sweep, 0)
            sweeps_received += 1
            surveys_received += len(sweep.surveys)
            for packet in packets:
                node_id = packet["node_id"]
                packet["sequence_number"] = sequence_numbers_by_node.get(node_id, 0)
                sequence_numbers_by_node[node_id] = packet["sequence_number"] + 1
                encoded = json.dumps(packet, separators=(",", ":")).encode("utf-8")
                sender.sendto(encoded, (target_host, target_port))
                packets_forwarded += 1
                if packet["type"] == "uwb_range":
                    anchors_seen.add(packet["data"]["anchor_id"])
                else:
                    anchors_seen.add(packet["node_id"])
                    anchors_seen.add(packet["data"]["peer_id"])
    except KeyboardInterrupt:
        pass
    finally:
        receiver.close()
        sender.close()
        if raw_output is not None:
            raw_output.close()
        print(
            "Adapter summary: "
            f"datagrams={sweeps_received}, surveys={surveys_received}, "
            f"packets={packets_forwarded}, "
            f"parse_errors={parse_errors}, anchors={sorted(anchors_seen)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert ESP32 DWM3000 sweep broadcasts to generic UWB range packets."
    )
    parser.add_argument("--listen-host", default=DEFAULT_LISTEN_HOST)
    parser.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT)
    parser.add_argument("--target-host", default=DEFAULT_TARGET_HOST)
    parser.add_argument("--target-port", type=int, default=DEFAULT_TARGET_PORT)
    parser.add_argument(
        "--raw-jsonl",
        type=Path,
        help="optional append-only raw sweep capture with PC arrival timestamps",
    )
    args = parser.parse_args()
    run_adapter(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        target_host=args.target_host,
        target_port=args.target_port,
        raw_jsonl=args.raw_jsonl,
    )


if __name__ == "__main__":
    main()
