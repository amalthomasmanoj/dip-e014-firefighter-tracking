"""合成 UDP 数据源：站立 -> 低姿态移动 -> 低姿态静止 -> 起立。
Synthetic UDP source: standing -> low posture moving -> low posture still -> stand up.

用途 / Purpose:
    python -m motion_monitor.demo_feed --port 9100
    python -m motion_monitor.live --port 9100
    python -m motion_monitor.dashboard --port 9100

它不是实验数据，只用于在没有硬件时验证实时链路和状态机。
It is not experimental data; it only exercises the live pipeline and state machine without hardware.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import socket
import time

from .core import GRAVITY, R_BS, mat_t_vec


def smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def angle_deg(t: float) -> float:
    """合成大腿倾角时间线。/ Synthetic thigh tilt timeline."""
    if t < 6.0:
        return 4.0
    if t < 11.0:
        # 低姿态移动：围绕 80° 摆动，仍高于 60° 阈值。
        # Low posture with movement around 80 degrees, still above the 60 degree threshold.
        return 80.0 + 8.0 * math.sin(2.0 * math.pi * 0.7 * t)
    if t < 18.0:
        return 90.0
    if t < 20.0:
        return 90.0 + (3.0 - 90.0) * smoothstep((t - 18.0) / 2.0)
    return 3.0


def yaw_rate_radps(t: float) -> float:
    """合成航向角速度：站立时转约 57°，低姿态时不再假装有可靠航向。
    Synthetic yaw rate: about 57 degrees while standing; no fake heading while low.
    """
    if 4.0 <= t < 6.0:
        return 0.50
    return 0.0


def packet_at(t: float, sequence: int, rng: random.Random) -> dict:
    angle = math.radians(angle_deg(t))
    # 静止比力的 body 表示；绕 body y 的倾角让 z 分量按 cos 减小。
    # Body specific force at rest; a body-y tilt reduces the z component by cos(angle).
    body_accel = (GRAVITY * math.sin(angle), 0.0, GRAVITY * math.cos(angle))
    pitch_rate = 0.0
    dt = 0.02
    pitch_rate = math.radians(angle_deg(t + dt) - angle_deg(t - dt)) / (2.0 * dt)
    body_gyro = (0.0, pitch_rate, yaw_rate_radps(t))
    sensor_accel = mat_t_vec(R_BS, body_accel)
    sensor_gyro = mat_t_vec(R_BS, body_gyro)
    # 加少量噪声，避免“完美零噪声”掩盖阈值问题。
    # Add a little noise so a perfect-zero stream does not hide threshold issues.
    accel = tuple(value + rng.gauss(0.0, 0.03) for value in sensor_accel)
    gyro = tuple(value + rng.gauss(0.0, 0.004) for value in sensor_gyro)
    return {
        "version": 1,
        "node_id": "synthetic",
        "sequence_number": sequence,
        "timestamp_us": int(round(t * 1e6)),
        "type": "imu",
        "data": {
            "ax_mps2": accel[0], "ay_mps2": accel[1], "az_mps2": accel[2],
            "gx_radps": gyro[0], "gy_radps": gyro[1], "gz_radps": gyro[2],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic IMU UDP source for the motion monitor."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--duration", type=float, default=24.0)
    parser.add_argument("--rate", type=float, default=50.0)
    args = parser.parse_args()
    if args.duration <= 0 or args.rate <= 0:
        parser.error("duration and rate must be positive")
    rng = random.Random(20261019)
    dt = 1.0 / args.rate
    sequence = 0
    start = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        print(f"Sending synthetic IMU to {args.host}:{args.port} for {args.duration:.0f}s", flush=True)
        print("Timeline: 0-4 stand, 4-6 turn left while standing, 6-11 low+moving, "
              "11-18 low+still, 18-20 stand up, 20-24 stand", flush=True)
        next_tick = start
        while True:
            now = time.monotonic()
            t = now - start
            if t >= args.duration:
                break
            packet = packet_at(t, sequence, rng)
            sock.sendto(json.dumps(packet).encode("utf-8"), (args.host, args.port))
            sequence += 1
            next_tick += dt
            sleep = next_tick - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
        print(f"Sent {sequence} packets.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
