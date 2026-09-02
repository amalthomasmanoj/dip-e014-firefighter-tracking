from __future__ import annotations


class McapWriter:
    """Placeholder adapter; preserve raw measurements when this is implemented."""

    def write(self, channel: str, payload: dict) -> None:
        raise NotImplementedError("MCAP writing is not wired in the bootstrap.")

