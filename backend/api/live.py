from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress

from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.ingestion.events import IngestedMeasurement
from backend.ingestion.pipeline import udp_measurement_events
from backend.models.measurements import UwbPairRangeMeasurement
from backend.models.state import websocket_message
from backend.uwb.anchor_map import LiveAnchorMapTracker
from backend.uwb.anchors import DEFAULT_ANCHORS, Anchor
from backend.uwb.live_ranges import LiveUwbRangeTracker


class LiveUdpStateHub:
    """Own the single UDP receiver and fan live estimator states out to clients."""

    def __init__(
        self,
        range_tracker: LiveUwbRangeTracker,
        anchors: tuple[Anchor, ...] = DEFAULT_ANCHORS,
        anchor_map_tracker: LiveAnchorMapTracker | None = None,
    ) -> None:
        self._range_tracker = range_tracker
        self._anchor_map_tracker = anchor_map_tracker
        self._anchors = anchors
        self._estimators: dict[str, DemoSensorEstimator] = {}
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._task: asyncio.Task[None] | None = None

    def process(self, event: IngestedMeasurement) -> str | None:
        self._range_tracker.observe(event)
        if self._anchor_map_tracker is not None and self._anchor_map_tracker.observe(event):
            self._anchors = self._anchor_map_tracker.anchors
            for estimator in self._estimators.values():
                estimator.set_anchors(self._anchors, reset_position=True)

        measurement = event.measurement
        if isinstance(measurement, UwbPairRangeMeasurement):
            return None
        estimator = self._estimators.get(measurement.node_id)
        if estimator is None:
            estimator = DemoSensorEstimator(anchors=self._anchors)
            self._estimators[measurement.node_id] = estimator
        state = estimator.update(measurement)
        if state is None:
            return None

        message = json.dumps(
            websocket_message(state, source="live", node_id=measurement.node_id)
        )
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
        return message

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
