from __future__ import annotations

import asyncio
import json

import pytest

from backend.api.websocket import fake_state_messages, serialize_state_message
from tools.fake_data.simulated_walk import simulated_state_stream


def test_fake_state_reaches_api_serialization() -> None:
    state = next(simulated_state_stream(sample_count=1))
    message = serialize_state_message(state)

    assert message["type"] == "estimated_state"
    assert message["source"] == "simulation"
    assert message["state"]["status"]["active_anchor_count"] == 3
    assert message["state"]["activity"]["posture"] == "standing"
    assert message["state"]["activity"]["motion"] == "walking"
    assert message["state"]["position_m"]["x"] >= 1.0


def test_fake_websocket_stream_uses_sensor_packet_pipeline() -> None:
    async def first_message() -> dict:
        stream = fake_state_messages(interval_s=0)
        return json.loads(await anext(stream))

    message = asyncio.run(first_message())

    assert message["type"] == "estimated_state"
    assert message["source"] == "simulation"
    assert message["state"]["status"]["active_anchor_count"] == 3
    assert message["state"]["position_m"]["x"] == pytest.approx(1.0)
    assert message["state"]["position_m"]["y"] == pytest.approx(1.0)
    assert message["state"]["activity"]["posture"] == "standing"
