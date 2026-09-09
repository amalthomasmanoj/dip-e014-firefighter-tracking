from __future__ import annotations

import os
from collections.abc import Mapping
from enum import Enum


SOURCE_ENV_VAR = "E014_SOURCE"


class SourceMode(str, Enum):
    SIMULATION = "simulation"
    UDP = "udp"
    REPLAY = "replay"

    @property
    def websocket_source(self) -> str:
        if self is SourceMode.UDP:
            return "live"
        return self.value

    @property
    def is_stream_available(self) -> bool:
        return self is SourceMode.SIMULATION


def parse_source_mode(value: str | None) -> SourceMode:
    if value is None:
        return SourceMode.SIMULATION

    normalized = value.strip().lower()
    try:
        return SourceMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in SourceMode)
        raise ValueError(
            f"Invalid {SOURCE_ENV_VAR}={value!r}; expected one of: {allowed}"
        ) from exc


def source_mode_from_env(env: Mapping[str, str] | None = None) -> SourceMode:
    environ = os.environ if env is None else env
    return parse_source_mode(environ.get(SOURCE_ENV_VAR))
