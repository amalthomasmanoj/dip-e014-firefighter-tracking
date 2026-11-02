import socket
from pathlib import Path

import yaml

from desktop.macos_app import (
    _available_tcp_port,
    _imu_mount_calibrated,
    _save_imu_mount_calibration,
)


def test_available_tcp_port_falls_back_when_preferred_port_is_busy() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        preferred = int(occupied.getsockname()[1])

        selected = _available_tcp_port(preferred)

    assert selected != preferred
    assert selected > 0


def test_saved_mount_calibration_is_reused(tmp_path: Path) -> None:
    path = tmp_path / "responders.yaml"
    path.write_text(
        "responders:\n"
        "  - responder_id: firefighter_1\n"
        "    uwb_node_id: tag_1\n"
        "    imu_node_id: waist_1\n"
        "    imu_mount_calibrated: false\n"
        "    imu_sensor_to_body: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]\n",
        encoding="utf-8",
    )

    _save_imu_mount_calibration(
        path,
        "firefighter_1",
        [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]],
    )

    decoded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert _imu_mount_calibrated(path) is True
    assert decoded["responders"][0]["imu_sensor_to_body"][2] == [1.0, 0.0, 0.0]
