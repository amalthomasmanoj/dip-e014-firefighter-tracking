from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from backend.config.source import SourceMode
from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.ingestion.pipeline import ingest_datagram
from backend.ingestion.sequencing import SequenceTracker
from backend.models.state import EstimatedState, websocket_message
from tools.fake_data.sensor_packets import simulated_sensor_frame_packet_stream


async def fake_state_messages(interval_s: float = 0.1) -> AsyncIterator[str]:
    while True:
        estimator = DemoSensorEstimator(emit_imu_only_state=False)
        tracker = SequenceTracker()
        for packet in simulated_sensor_frame_packet_stream():
            event = ingest_datagram(
                payload=json.dumps(packet).encode("utf-8"),
                tracker=tracker,
                arrival_time_s=packet["timestamp_us"] / 1_000_000,
            )
            state = estimator.update(event.measurement)
            if state is not None:
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
