from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from backend.models.state import EstimatedState, websocket_message
from tools.fake_data.simulated_walk import simulated_state_stream


async def fake_state_messages(interval_s: float = 0.1) -> AsyncIterator[str]:
    while True:
        for state in simulated_state_stream():
            yield json.dumps(websocket_message(state, source="simulation"))
            await asyncio.sleep(interval_s)


def serialize_state_message(state: EstimatedState) -> dict:
    return websocket_message(state, source="simulation")

