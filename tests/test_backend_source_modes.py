from __future__ import annotations

import pytest

from backend.api.app import create_app
from backend.api.websocket import serialize_state_message
from backend.config.source import SourceMode, parse_source_mode, source_mode_from_env
from tools.fake_data.simulated_walk import simulated_state_stream


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, SourceMode.SIMULATION),
        ("simulation", SourceMode.SIMULATION),
        ("udp", SourceMode.UDP),
        ("replay", SourceMode.REPLAY),
    ],
)
def test_parse_source_mode_accepts_supported_values(
    raw_value: str | None,
    expected: SourceMode,
) -> None:
    assert parse_source_mode(raw_value) is expected


def test_parse_source_mode_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid E014_SOURCE='hardware'"):
        parse_source_mode("hardware")


def test_source_mode_from_env_defaults_to_simulation() -> None:
    assert source_mode_from_env({}) is SourceMode.SIMULATION


def test_source_mode_from_env_uses_e014_source() -> None:
    assert source_mode_from_env({"E014_SOURCE": "replay"}) is SourceMode.REPLAY


def test_serialize_state_message_maps_udp_to_contract_live_source() -> None:
    state = next(simulated_state_stream(sample_count=1))

    message = serialize_state_message(state, source_mode=SourceMode.UDP)

    assert message["source"] == "live"


@pytest.mark.parametrize(
    ("source_mode", "source_status"),
    [
        (SourceMode.SIMULATION, "available"),
        (SourceMode.UDP, "not_implemented"),
        (SourceMode.REPLAY, "not_implemented"),
    ],
)
def test_health_reports_active_source_mode(
    source_mode: SourceMode,
    source_status: str,
) -> None:
    app = create_app(source_mode=source_mode)
    health_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/health"
    )

    assert health_route.endpoint() == {
        "status": "ok",
        "source": source_mode.value,
        "source_status": source_status,
    }
