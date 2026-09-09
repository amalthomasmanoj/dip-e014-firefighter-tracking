from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
from tools.fake_data.sensor_packets import (
    DEFAULT_DT_S,
    DEFAULT_START_US,
    path_pose,
    simulated_imu_packet_stream,
    simulated_mixed_packet_stream,
    simulated_uwb_range_packet_stream,
    timestamp_for_index,
)


def _heading_to_quaternion(yaw_rad: float) -> Quaternion:
    half = yaw_rad / 2.0
    return Quaternion(x=0.0, y=0.0, z=math.sin(half), w=math.cos(half))


def simulated_state_stream(sample_count: int = 90, dt_s: float = DEFAULT_DT_S) -> Iterator[EstimatedState]:
    for index in range(sample_count):
        x, y, vx, vy, yaw, stopped = path_pose(index=index, dt_s=dt_s)

        uncertainty = 0.2 + 0.005 * index
        yield EstimatedState(
            timestamp_us=timestamp_for_index(index=index, start_us=DEFAULT_START_US, dt_s=dt_s),
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
    parser.add_argument(
        "--kind",
        choices=("state", "imu", "uwb", "mixed"),
        default="state",
        help="fake output kind: estimated state or contract sensor packets",
    )
    args = parser.parse_args()
    if args.kind == "state":
        for state in simulated_state_stream(sample_count=args.count):
            print(json.dumps(state.to_dict()))
        return

    if args.kind == "imu":
        stream = simulated_imu_packet_stream(packet_count=args.count)
    elif args.kind == "uwb":
        stream = simulated_uwb_range_packet_stream(packet_count=args.count)
    else:
        stream = simulated_mixed_packet_stream(packet_count=args.count)

    for packet in stream:
        print(json.dumps(packet))


if __name__ == "__main__":
    main()
