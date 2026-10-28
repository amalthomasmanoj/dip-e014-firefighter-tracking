"""Scripted IMU scenarios for exercising heading and posture classification.

Generates contract-valid `imu` packets for a named scenario so heading and
posture code can be tested without hardware, and can stream them over UDP to
the live backend.

This is a contract and integration tool. The accelerations are posed body
attitudes plus light noise, not a physics-grade inertial simulation, so it
proves the pipeline and the classifier bands, never sensor realism.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import socket
import time
from collections.abc import Iterator
from typing import Any

GRAVITY_MPS2 = 9.80665
DEFAULT_NODE_ID = "wearable_01"
DEFAULT_START_SEQUENCE = 1
DEFAULT_START_US = 1_000_000
DEFAULT_DT_S = 0.02

# tilt of the sensor's up-axis away from world up, in radians
POSTURE_TILT_RAD = {
    "standing": 0.0,
    "crouching": 0.9,
    "lying_down": math.pi / 2.0,
}

Scenario = str
SCENARIOS: tuple[Scenario, ...] = (
    "standing",
    "walking",
    "crouching",
    "lying_down",
    "turn",
    "fall",
    "full",
)


def _segments_for(scenario: Scenario) -> list[tuple[str, float, float, float]]:
    """Return (posture, duration_s, yaw_rate_radps, step_amplitude) segments."""
    if scenario == "standing":
        return [("standing", 6.0, 0.0, 0.0)]
    if scenario == "walking":
        return [("standing", 6.0, 0.0, 1.6)]
    if scenario == "crouching":
        return [("crouching", 6.0, 0.0, 0.0)]
    if scenario == "lying_down":
        return [("lying_down", 6.0, 0.0, 0.0)]
    if scenario == "turn":
        # Calibrate while still, then make a full 360-degree turn at 45 deg/s.
        return [
            ("standing", 2.0, 0.0, 0.0),
            ("standing", 8.0, math.radians(45.0), 1.6),
        ]
    if scenario == "fall":
        return [
            ("standing", 4.0, 0.0, 1.6),
            ("lying_down", 8.0, 0.0, 0.0),
        ]
    if scenario == "full":
        return [
            ("standing", 4.0, 0.0, 0.0),
            ("standing", 5.0, 0.0, 1.6),
            ("standing", 4.0, math.radians(45.0), 1.6),
            ("crouching", 5.0, 0.0, 0.0),
            ("standing", 3.0, 0.0, 1.6),
            ("lying_down", 6.0, 0.0, 0.0),
        ]
    raise ValueError(f"unknown scenario {scenario!r}; expected one of {list(SCENARIOS)}")


def imu_packet_stream(
    scenario: Scenario = "full",
    dt_s: float = DEFAULT_DT_S,
    node_id: str = DEFAULT_NODE_ID,
    start_sequence_number: int = DEFAULT_START_SEQUENCE,
    start_us: int = DEFAULT_START_US,
    noise_mps2: float = 0.04,
    seed: int = 7,
) -> Iterator[dict[str, Any]]:
    """Yield contract-valid IMU packets for one pass of the scenario."""
    if dt_s <= 0.0:
        raise ValueError("dt_s must be positive")

    rng = random.Random(seed)
    sequence_number = start_sequence_number
    timestamp_us = start_us

    for posture, duration_s, yaw_rate_radps, step_amplitude in _segments_for(scenario):
        tilt_rad = POSTURE_TILT_RAD[posture]
        sample_count = max(1, int(round(duration_s / dt_s)))
        for index in range(sample_count):
            t = index * dt_s
            # Gravity projected onto a body tilted by `tilt_rad`.
            az = GRAVITY_MPS2 * math.cos(tilt_rad)
            ax = GRAVITY_MPS2 * math.sin(tilt_rad)
            # Walking adds a vertical bob and fore-aft sway at ~2 Hz.
            if step_amplitude:
                stride = math.sin(2.0 * math.pi * 2.0 * t)
                az += step_amplitude * stride
                ax += step_amplitude * 0.5 * math.cos(2.0 * math.pi * 2.0 * t)

            yield {
                "version": 1,
                "node_id": node_id,
                "sequence_number": sequence_number,
                "timestamp_us": timestamp_us,
                "type": "imu",
                "data": {
                    "ax_mps2": ax + rng.gauss(0.0, noise_mps2),
                    "ay_mps2": rng.gauss(0.0, noise_mps2),
                    "az_mps2": az + rng.gauss(0.0, noise_mps2),
                    "gx_radps": rng.gauss(0.0, 0.01),
                    "gy_radps": rng.gauss(0.0, 0.01),
                    "gz_radps": yaw_rate_radps + rng.gauss(0.0, 0.01),
                },
            }
            sequence_number += 1
            timestamp_us += int(dt_s * 1_000_000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="full")
    parser.add_argument("--dt-s", type=float, default=DEFAULT_DT_S)
    parser.add_argument(
        "--udp",
        action="store_true",
        help="stream to the backend instead of printing JSON lines",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="pace packets at dt-s instead of sending as fast as possible",
    )
    args = parser.parse_args()

    if not args.udp:
        for packet in imu_packet_stream(scenario=args.scenario, dt_s=args.dt_s):
            print(json.dumps(packet))
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sequence_number = DEFAULT_START_SEQUENCE
    start_us = DEFAULT_START_US
    sent = 0
    print(
        f"streaming scenario {args.scenario!r} to {args.host}:{args.port} "
        f"at dt={args.dt_s}s (Ctrl-C to stop)"
    )
    try:
        while True:
            last_packet = None
            for packet in imu_packet_stream(
                scenario=args.scenario,
                dt_s=args.dt_s,
                start_sequence_number=sequence_number,
                start_us=start_us,
            ):
                sock.sendto(json.dumps(packet).encode("utf-8"), (args.host, args.port))
                last_packet = packet
                sent += 1
                if args.realtime:
                    time.sleep(args.dt_s)
            if last_packet is not None:
                # Continue sequence and time across loops so the backend's
                # sequence tracker and staleness checks stay happy.
                sequence_number = last_packet["sequence_number"] + 1
                start_us = last_packet["timestamp_us"] + int(args.dt_s * 1_000_000)
            print(f"  sent {sent} packets")
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print(f"sent {sent} packets")


if __name__ == "__main__":
    main()
