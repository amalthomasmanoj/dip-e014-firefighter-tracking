from __future__ import annotations

import argparse
import json
import socket
import time

from backend.ingestion.parser import parse_packet
from backend.models.measurements import ImuMeasurement


def receive(host: str, port: int, duration_s: float) -> tuple[int, int]:
    valid = 0
    failures = 0
    latest: ImuMeasurement | None = None
    started = time.monotonic()
    next_report = started + 1.0
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.settimeout(0.25)
    receiver.bind((host, port))
    try:
        while time.monotonic() - started < duration_s:
            try:
                payload, _sender = receiver.recvfrom(65_535)
            except TimeoutError:
                payload = b""
            if payload:
                try:
                    decoded = json.loads(payload)
                    measurement = parse_packet(decoded)
                    if not isinstance(measurement, ImuMeasurement):
                        raise TypeError("packet is not an IMU measurement")
                except (UnicodeDecodeError, ValueError, TypeError):
                    failures += 1
                else:
                    valid += 1
                    latest = measurement
            now = time.monotonic()
            if now >= next_report:
                elapsed = max(now - started, 1e-9)
                sample = "waiting"
                if latest is not None:
                    sample = (
                        f"node={latest.node_id} "
                        f"accel=({latest.ax_mps2:.3f},{latest.ay_mps2:.3f},{latest.az_mps2:.3f}) "
                        f"gyro=({latest.gx_radps:.3f},{latest.gy_radps:.3f},{latest.gz_radps:.3f})"
                    )
                print(
                    f"valid={valid} failures={failures} average_hz={valid / elapsed:.1f} {sample}",
                    flush=True,
                )
                next_report = now + 1.0
    finally:
        receiver.close()
    return valid, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate physical IMU UDP packets")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--duration-s", type=float, default=30.0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65_535:
        parser.error("--port must be between 0 and 65535")
    if args.duration_s <= 0:
        parser.error("--duration-s must be positive")
    valid, failures = receive(args.host, args.port, args.duration_s)
    print(f"complete valid={valid} failures={failures}")
    if valid == 0 or failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
