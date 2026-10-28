from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from backend.ingestion.events import IngestedMeasurement
from backend.models.measurements import UwbRangeMeasurement


@dataclass(frozen=True)
class _ObservedRange:
    measurement: UwbRangeMeasurement
    arrival_time_s: float


class LiveUwbRangeTracker:
    """Keep a short-lived, read-only view of ranges received by ingestion."""

    def __init__(
        self,
        stale_after_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if stale_after_s <= 0.0:
            raise ValueError("stale_after_s must be positive")
        self._stale_after_s = stale_after_s
        self._clock = clock
        self._ranges: dict[tuple[str, str], _ObservedRange] = {}

    def observe(self, event: IngestedMeasurement) -> None:
        measurement = event.measurement
        if not isinstance(measurement, UwbRangeMeasurement):
            return

        key = (measurement.node_id, measurement.anchor_id)
        if not measurement.valid:
            self._ranges.pop(key, None)
            return

        self._ranges[key] = _ObservedRange(
            measurement=measurement,
            arrival_time_s=event.arrival_time_s,
        )

    def snapshot(
        self,
        now_s: float | None = None,
        node_id: str | None = None,
    ) -> dict[str, object]:
        current_time_s = self._clock() if now_s is None else now_s
        active = {
            key: observed
            for key, observed in self._ranges.items()
            if 0.0 <= current_time_s - observed.arrival_time_s <= self._stale_after_s
        }

        if not active:
            return {
                "source": "live",
                "tag_node_id": None,
                "tag_present": False,
                "latest_timestamp_us": None,
                "active_anchor_count": 0,
                "ranges": [],
            }

        latest_node_id = node_id or max(
            active.values(),
            key=lambda observed: observed.arrival_time_s,
        ).measurement.node_id
        node_ranges = [
            observed
            for (node_id, _anchor_id), observed in active.items()
            if node_id == latest_node_id
        ]
        if not node_ranges:
            return {
                "source": "live",
                "tag_node_id": node_id,
                "tag_present": False,
                "latest_timestamp_us": None,
                "active_anchor_count": 0,
                "ranges": [],
            }
        node_ranges.sort(key=lambda observed: observed.measurement.anchor_id)

        return {
            "source": "live",
            "tag_node_id": latest_node_id,
            "tag_present": True,
            "latest_timestamp_us": max(
                observed.measurement.timestamp_us for observed in node_ranges
            ),
            "active_anchor_count": len(node_ranges),
            "ranges": [
                {
                    "anchor_id": observed.measurement.anchor_id,
                    "range_m": observed.measurement.range_m,
                    "measurement_timestamp_us": observed.measurement.timestamp_us,
                    "age_s": current_time_s - observed.arrival_time_s,
                }
                for observed in node_ranges
            ],
        }
