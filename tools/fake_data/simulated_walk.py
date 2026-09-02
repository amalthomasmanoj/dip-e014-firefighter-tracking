from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterator

from backend.models.state import (
    EstimatedState,
    Quaternion,
    SensorStatus,
    Uncertainty,
    Vector3,
)


def _heading_to_quaternion(yaw_rad: float) -> Quaternion:
    half = yaw_rad / 2.0
    return Quaternion(x=0.0, y=0.0, z=math.sin(half), w=math.cos(half))


def simulated_state_stream(sample_count: int = 90, dt_s: float = 0.1) -> Iterator[EstimatedState]:
    start_us = 1_000_000
    for index in range(sample_count):
        t = index * dt_s
        if t < 3.0:
            x = 1.0 + 0.8 * t
            y = 1.0
            vx = 0.8
            vy = 0.0
            yaw = 0.0
            stopped = False
        elif t < 6.0:
            x = 3.4
            y = 1.0 + 0.7 * (t - 3.0)
            vx = 0.0
            vy = 0.7
            yaw = math.pi / 2.0
            stopped = False
        else:
            x = 3.4
            y = 3.1
            vx = 0.0
            vy = 0.0
            yaw = math.pi / 2.0
            stopped = True

        uncertainty = 0.2 + 0.005 * index
        yield EstimatedState(
            timestamp_us=start_us + int(t * 1_000_000),
            position_m=Vector3(x=x, y=y, z=0.0),
            velocity_mps=Vector3(x=vx, y=vy, z=0.0),
            orientation_xyzw=_heading_to_quaternion(yaw),
            uncertainty=Uncertainty(
                sigma_x_m=uncertainty,
                sigma_y_m=uncertainty * 1.2,
                sigma_z_m=1.0,
            ),
            status=SensorStatus(
                zupt_active=stopped,
                uwb_available=True,
                active_anchor_count=3,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    for state in simulated_state_stream(sample_count=args.count):
        print(json.dumps(state.to_dict()))


if __name__ == "__main__":
    main()

