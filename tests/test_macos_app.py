import socket

from desktop.macos_app import _available_tcp_port


def test_available_tcp_port_falls_back_when_preferred_port_is_busy() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        preferred = int(occupied.getsockname()[1])

        selected = _available_tcp_port(preferred)

    assert selected != preferred
    assert selected > 0
