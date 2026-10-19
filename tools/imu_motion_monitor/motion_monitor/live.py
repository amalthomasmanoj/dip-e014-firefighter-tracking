"""实时 UDP 监测入口：方向 + 低姿态/静止候选。
Live UDP entry point: direction plus low-posture / immobility candidates.

运行 / Run:
    python -m motion_monitor.live --port 9000

默认监听 9000，与 DIP 固件现有发送端口一致；不要和根目录的
live_zupt_receiver.py 同时占用同一端口。
Defaults to port 9000, matching the existing DIP firmware; do not run it at the same time as
the root live_zupt_receiver.py on the same port.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import socket
import time
from pathlib import Path
from typing import TextIO

from .core import Monitor, MonitorConfig, Status
from .protocol import parse_imu_packet


def build_config(args: argparse.Namespace) -> MonitorConfig:
    return MonitorConfig(
        low_enter_deg=args.low_enter_deg,
        low_exit_deg=args.low_exit_deg,
        immobile_s=args.immobile_s,
        motion_gyro_radps=args.motion_gyro,
        motion_accel_mps2=args.motion_accel,
        warmup_s=args.warmup_s,
    )


def format_status(status: Status) -> str:
    direction = "--" if status.direction_deg is None else f"{status.direction_deg:+7.1f} deg"
    posture = "--" if status.posture_deg is None else f"{status.posture_deg:5.1f} deg"
    return (
        f"t={status.t_s:7.2f}s | {status.state:<12s} | dir={direction} | "
        f"thigh={posture} | motion={status.motion_score:5.2f} | "
        f"still={status.immobile_s:5.1f}s | {status.bias_quality}"
    )


def print_status(status: Status, previous_state: str | None) -> None:
    if status.state != previous_state:
        print(f"\n*** {status.state}: {status.label} ({status.reason}) ***", flush=True)
    print(format_status(status), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live UDP monitor: relative motion direction and low-posture/immobility candidates."
    )
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--duration", type=float, default=0.0, help="seconds after first valid packet; 0 = unlimited")
    parser.add_argument("--csv", type=Path, default=None, help="optional CSV log path")
    parser.add_argument("--low-enter-deg", type=float, default=60.0)
    parser.add_argument("--low-exit-deg", type=float, default=50.0)
    parser.add_argument("--immobile-s", type=float, default=5.0)
    parser.add_argument("--motion-gyro", type=float, default=0.12, help="angular-rate motion threshold (rad/s)")
    parser.add_argument("--motion-accel", type=float, default=0.35, help="acceleration-dynamics threshold (m/s^2)")
    parser.add_argument("--warmup-s", type=float, default=2.0, help="initial still calibration seconds")
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration < 0:
        parser.error("duration must be finite and non-negative")
    try:
        config = build_config(args)
    except ValueError as error:
        parser.error(str(error))

    monitor = Monitor(config)
    counts = {"valid": 0, "invalid": 0, "foreign_sender": 0, "ack_failures": 0}
    peer: tuple[str, int] | None = None
    start: float | None = None
    last_report = 0.0
    last_state: str | None = None
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

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.bind((args.bind, args.port))
        except OSError as error:
            parser.exit(1, f"Cannot bind UDP {args.port}: {error}\nClose the other receiver first.\n")
        sock.settimeout(0.05)
        print(f"Listening on {args.bind}:{args.port}", flush=True)
        print("Start standing still for about 2 s; direction is relative to the start heading.", flush=True)
        print("This is a status prototype, not a safety-certified alarm.\n", flush=True)
        try:
            while True:
                now = time.monotonic()
                if start is not None and args.duration and now - start >= args.duration:
                    break
                try:
                    raw, sender = sock.recvfrom(65535)
                except socket.timeout:
                    status = monitor.tick(now)
                    if status.state != last_state:
                        print_status(status, last_state)
                        last_state = status.state
                    continue
                if raw.startswith(b"DIP_PING "):
                    token = raw[9:]
                    if len(token) == 16 and all(c in b"0123456789abcdef" for c in token):
                        try:
                            sock.sendto(b"DIP_ACK " + token, sender)
                        except OSError:
                            counts["ack_failures"] += 1
                    continue
                try:
                    packet = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeError, OverflowError):
                    counts["invalid"] += 1
                    continue
                if peer is not None and sender != peer:
                    counts["foreign_sender"] += 1
                    continue
                parsed = parse_imu_packet(packet)
                if parsed is None:
                    counts["invalid"] += 1
                    continue
                if peer is None:
                    peer = sender
                if start is None:
                    start = now
                    print(f"First IMU packet from {sender[0]}:{sender[1]}", flush=True)
                timestamp_us, sequence, accel, gyro = parsed
                status = monitor.ingest(
                    timestamp_us / 1e6, accel, gyro, sequence=sequence, host_s=now
                )
                counts["valid"] += 1
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
                if now - last_report >= 0.5 or status.state != last_state:
                    print_status(status, last_state)
                    last_report = now
                    last_state = status.state
        except KeyboardInterrupt:
            print("\nStopped by user.", flush=True)
        finally:
            if csv_file is not None:
                csv_file.flush()
                csv_file.close()

    final = monitor.last_status
    print(f"\nSummary: valid={counts['valid']} invalid={counts['invalid']} "
          f"foreign={counts['foreign_sender']} ack_failures={counts['ack_failures']}", flush=True)
    if final is not None:
        print("Final:", format_status(final), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
