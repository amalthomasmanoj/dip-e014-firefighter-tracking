import socket
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import yaml

from desktop.macos_app import (
    HostController,
    _available_tcp_port,
    _cloudflared_download_name,
    _imu_mount_calibrated,
    _load_heart_rate_config,
    _load_host_mode,
    _save_heart_rate_config,
    _save_host_mode,
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


def test_windows_cloudflared_download_uses_executable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    assert _cloudflared_download_name() == "cloudflared-windows-amd64.exe"


def test_heart_rate_configuration_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "heart_rate.json"
    config = {
        "device": " H808S ",
        "wearer": " Firefighter Min ",
        "responder_id": "firefighter_1",
    }

    _save_heart_rate_config(path, config)

    assert _load_heart_rate_config(path, ["firefighter_1"]) == {
        "device": "H808S",
        "wearer": "Firefighter Min",
        "responder_id": "firefighter_1",
    }


def test_heart_rate_configuration_reassigns_removed_responder(tmp_path: Path) -> None:
    path = tmp_path / "heart_rate.json"
    _save_heart_rate_config(
        path,
        {"device": "H808S", "wearer": "Min", "responder_id": "removed"},
    )

    assert _load_heart_rate_config(path, ["firefighter_1"])["responder_id"] == "firefighter_1"


def test_host_mode_round_trip_and_invalid_fallback(tmp_path: Path) -> None:
    path = tmp_path / "host.json"
    assert _load_host_mode(path) == "simulation"

    _save_host_mode(path, "udp")
    assert _load_host_mode(path) == "udp"

    path.write_text('{"mode": "unknown"}\n', encoding="utf-8")
    assert _load_host_mode(path) == "simulation"


def test_mount_calibration_keeps_live_backend_running(monkeypatch, tmp_path: Path) -> None:
    controller = HostController.__new__(HostController)
    controller._lock = threading.RLock()
    controller.mode = "udp"
    controller.port = 8123
    controller.backend = SimpleNamespace(poll=lambda: None)
    controller.responder_config = tmp_path / "responders.yaml"
    controller.get_status = lambda: {"running": True, "mode": "udp"}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self) -> bytes:
            return b'{"imu_sensor_to_body": [[1,0,0],[0,1,0],[0,0,1]]}'

    monkeypatch.setattr("desktop.macos_app.urllib.request.urlopen", lambda *_a, **_k: Response())
    saved: list[tuple[Path, str, object]] = []
    monkeypatch.setattr(
        "desktop.macos_app._save_imu_mount_calibration",
        lambda path, responder_id, transform: saved.append((path, responder_id, transform)),
    )
    monkeypatch.setattr(
        controller,
        "_stop_locked",
        lambda: (_ for _ in ()).throw(AssertionError("backend must not restart")),
    )

    assert controller.calibrate_imu_mount("firefighter_1") == {"running": True, "mode": "udp"}
    assert saved[0][0:2] == (controller.responder_config, "firefighter_1")
