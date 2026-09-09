from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from backend.config.source import SourceMode
from backend.models.state import EstimatedState, websocket_message
from tools.fake_data.simulated_walk import simulated_state_stream


async def fake_state_messages(interval_s: float = 0.1) -> AsyncIterator[str]:
    while True:
        for state in simulated_state_stream():
            yield json.dumps(websocket_message(state, source="simulation"))
            await asyncio.sleep(interval_s)


def state_messages_for_source(
    source_mode: SourceMode,
    interval_s: float = 0.1,
) -> AsyncIterator[str]:
    if source_mode is SourceMode.SIMULATION:
        return fake_state_messages(interval_s=interval_s)

    raise NotImplementedError(f"{source_mode.value} state streaming is not implemented")


def serialize_state_message(
    state: EstimatedState,
    source_mode: SourceMode = SourceMode.SIMULATION,
) -> dict:
    return websocket_message(state, source=source_mode.websocket_source)
