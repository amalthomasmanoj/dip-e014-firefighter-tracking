from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator


async def receive_udp_packets(host: str = "0.0.0.0", port: int = 9000) -> AsyncIterator[bytes]:
    """Yield UDP datagrams without parsing estimator-specific content."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.setblocking(False)
    loop = asyncio.get_running_loop()
    try:
        while True:
            data, _addr = await loop.sock_recvfrom(sock, 65535)
            yield data
    finally:
        sock.close()

