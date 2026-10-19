"""离线回放一份 DIP 录制，输出方向/低姿态状态，不修改原始数据。
Offline replay of one DIP recording; prints direction/posture states without modifying raw data.

运行 / Run:
    python -m motion_monitor.replay --recording live_recordings/20261018_212645_195445_live
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import TextIO

from .core import Monitor, MonitorConfig, Status
from .protocol import parse_imu_packet


def status_line(status: Status) -> str:
    direction = "--" if status.direction_deg is None else f"{status.direction_deg:+7.1f} deg"
    posture = "--" if status.posture_deg is None else f"{status.posture_deg:5.1f} deg"
    return (
        f"{status.t_s:7.2f}s {status.state:<12s} dir={direction} "
        f"thigh={posture} motion={status.motion_score:5.2f} still={status.immobile_s:5.1f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline replay of a DIP recording: relative direction and low-posture status."
    )
    parser.add_argument("--recording", type=Path, required=True, help="recording directory or packets.jsonl")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--every", type=float, default=1.0, help="print interval in host seconds; 0 = state changes only")
    parser.add_argument("--start", type=float, default=0.0, help="host receive-relative start second")
    parser.add_argument("--end", type=float, default=None, help="host receive-relative end second")
    parser.add_argument("--low-enter-deg", type=float, default=60.0)
    parser.add_argument("--low-exit-deg", type=float, default=50.0)
    parser.add_argument("--immobile-s", type=float, default=5.0)
    parser.add_argument("--motion-gyro", type=float, default=0.12)
    parser.add_argument("--motion-accel", type=float, default=0.35)
    parser.add_argument("--warmup-s", type=float, default=2.0)
    args = parser.parse_args()

    path = args.recording / "packets.jsonl" if args.recording.is_dir() else args.recording
    if not path.is_file():
        parser.error(f"packets.jsonl not found: {path}")
    monitor = Monitor(MonitorConfig(
        low_enter_deg=args.low_enter_deg,
        low_exit_deg=args.low_exit_deg,
        immobile_s=args.immobile_s,
        motion_gyro_radps=args.motion_gyro,
        motion_accel_mps2=args.motion_accel,
        warmup_s=args.warmup_s,
    ))

    csv_file: TextIO | None = None
    writer: csv.writer | None = None
    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        csv_file = args.csv.open("w", newline="", encoding="utf-8")
        writer = csv.writer(csv_file)
        writer.writerow([
            "host_time", "node_time", "state", "direction_deg", "direction_valid",
            "posture_deg", "posture_raw_deg", "low_posture", "moving", "motion_score",
            "gyro_rate_radps", "accel_dynamic_mps2", "immobile_s", "low_duration_s",
            "bias_quality", "reason", "samples",
        ])

    first_host: float | None = None
    last_report = -1e9
    last_state: str | None = None
    counts: Counter[str] = Counter()
    heading_values: list[float] = []
    max_posture = 0.0
    final: Status | None = None

    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    packet = record.get("packet")
                    parsed = parse_imu_packet(packet)
                    if parsed is None:
                        counts["invalid"] += 1
                        continue
                    host_ns = record.get("arrival_monotonic_ns")
                    timestamp_us, sequence, accel, gyro = parsed
                    if host_ns is None:
                        host_s = timestamp_us / 1e6
                    else:
                        host_s = float(host_ns) / 1e9
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    counts["invalid"] += 1
                    continue
                if first_host is None:
                    first_host = host_s
                host_rel = host_s - first_host
                if host_rel < args.start:
                    continue
                if args.end is not None and host_rel > args.end:
                    break
                status = monitor.ingest(
                    timestamp_us / 1e6, accel, gyro, sequence=sequence, host_s=host_s
                )
                final = status
                counts[status.state] += 1
                if status.direction_deg is not None:
                    heading_values.append(status.direction_deg)
                if status.posture_deg is not None:
                    max_posture = max(max_posture, status.posture_deg)
                if writer is not None and csv_file is not None:
                    writer.writerow([
                        f"{status.t_s:.6f}", f"{status.node_s:.6f}", status.state,
                        "" if status.direction_deg is None else f"{status.direction_deg:.6f}",
                        int(status.direction_valid),
                        "" if status.posture_deg is None else f"{status.posture_deg:.6f}",
                        "" if status.posture_raw_deg is None else f"{status.posture_raw_deg:.6f}",
                        int(status.low_posture), int(status.moving), f"{status.motion_score:.6f}",
                        f"{status.gyro_rate_radps:.6f}", f"{status.accel_dynamic_mps2:.6f}",
                        f"{status.immobile_s:.3f}", f"{status.low_duration_s:.3f}",
                        status.bias_quality, status.reason, status.samples,
                    ])
                if status.state != last_state:
                    print(f"*** {status.state}: {status.label} ({status.reason})", flush=True)
                    last_state = status.state
                if args.every > 0 and host_rel - last_report >= args.every:
                    print(status_line(status), flush=True)
                    last_report = host_rel
    finally:
        if csv_file is not None:
            csv_file.close()

    print(f"\nFile: {path}")
    print(f"States: {dict(counts)}")
    if final is not None:
        print(f"Final: {status_line(final)}")
        print(f"Bias quality: {final.bias_quality}; samples: {final.samples}")
    if heading_values:
        print(f"Relative heading range: {min(heading_values):+.1f} .. {max(heading_values):+.1f} deg")
    print(f"Maximum low-passed thigh tilt: {max_posture:.1f} deg")
    print("Direction is relative to the start heading; it is not an absolute bearing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
