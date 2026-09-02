from __future__ import annotations

from backend.api.websocket import serialize_state_message
from tools.fake_data.simulated_walk import simulated_state_stream


def test_fake_state_reaches_api_serialization() -> None:
    state = next(simulated_state_stream(sample_count=1))
    message = serialize_state_message(state)

    assert message["type"] == "estimated_state"
    assert message["source"] == "simulation"
    assert message["state"]["status"]["active_anchor_count"] == 3
    assert message["state"]["position_m"]["x"] >= 1.0

