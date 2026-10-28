from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Callable

from backend.config.plugins import (
    activity_classifier_from_env,
    heading_estimator_from_env,
)
from backend.config.responders import ResponderConfig, ResponderRegistry
from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.ingestion.events import IngestedMeasurement
from backend.ingestion.pipeline import udp_measurement_events
from backend.models.state import websocket_message
from backend.uwb.anchors import DEFAULT_ANCHORS, Anchor
from backend.uwb.live_ranges import LiveUwbRangeTracker


class LiveUdpStateHub:
    """Own the single UDP receiver and fan live estimator states out to clients."""

    def __init__(
        self,
        range_tracker: LiveUwbRangeTracker,
        anchors: tuple[Anchor, ...] = DEFAULT_ANCHORS,
        responders: tuple[ResponderConfig, ...] = (),
        estimator_factory: Callable[[], DemoSensorEstimator] | None = None,
    ) -> None:
        self._range_tracker = range_tracker
        self._registry = ResponderRegistry(responders)
        self._estimator_factory = estimator_factory or (
            lambda: DemoSensorEstimator(
                anchors=anchors,
                heading_estimator=heading_estimator_from_env(),
                activity_classifier=activity_classifier_from_env(),
            )
        )
        self._estimators: dict[str, DemoSensorEstimator] = {}
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._task: asyncio.Task[None] | None = None

    def process(self, event: IngestedMeasurement) -> str | None:
        self._range_tracker.observe(event)
        responder_id, measurement = self._registry.resolve(event.measurement)
        estimator = self._estimators.get(responder_id)
        if estimator is None:
            estimator = self._estimator_factory()
            self._estimators[responder_id] = estimator
        state = estimator.update(measurement)
        if state is None:
            return None

        message = json.dumps(websocket_message(state, source="live", node_id=responder_id))
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
        return message

    def align_heading(self, responder_id: str, heading_rad: float) -> None:
        estimator = self._estimators.get(responder_id)
        if estimator is None:
            raise KeyError(responder_id)
        estimator.align_heading(heading_rad)

    async def _run(self) -> None:
        async for event in udp_measurement_events():
            self.process(event)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
            await asyncio.sleep(0)
            if self._task.done():
                await self._task

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def messages(self) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)
