from __future__ import annotations

import math
import statistics
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from backend.ingestion.events import IngestedMeasurement
from backend.models.measurements import UwbPairRangeMeasurement
from backend.uwb.anchors import Anchor


@dataclass(frozen=True)
class _PairObservation:
    measurement: UwbPairRangeMeasurement
    arrival_time_s: float
    accepted: bool


def _pair_key(first_id: str, second_id: str) -> tuple[str, str]:
    return tuple(sorted((first_id, second_id)))


def solve_three_anchor_map(
    anchor_ids: Sequence[str],
    pair_ranges_m: dict[tuple[str, str], float],
) -> tuple[Anchor, Anchor, Anchor]:
    """Solve a deterministic 2-D relative frame from three pairwise ranges."""
    if len(anchor_ids) != 3 or len(set(anchor_ids)) != 3:
        raise ValueError("exactly three unique anchor IDs are required")

    origin_id, x_axis_id, positive_y_id = anchor_ids
    d12 = pair_ranges_m[_pair_key(origin_id, x_axis_id)]
    d13 = pair_ranges_m[_pair_key(origin_id, positive_y_id)]
    d23 = pair_ranges_m[_pair_key(x_axis_id, positive_y_id)]
    if min(d12, d13, d23) <= 0.0:
        raise ValueError("pairwise ranges must be positive")
    if d12 > d13 + d23 or d12 < abs(d13 - d23):
        raise ValueError("pairwise ranges do not form a triangle")

    x3 = (d13**2 - d23**2 + d12**2) / (2.0 * d12)
    y_squared = d13**2 - x3**2
    if y_squared < -1e-9:
        raise ValueError("pairwise ranges produce invalid triangle geometry")
    y3 = math.sqrt(max(0.0, y_squared))
    if y3 <= 1e-3:
        raise ValueError("anchor geometry is collinear")

    return (
        Anchor(origin_id, 0.0, 0.0),
        Anchor(x_axis_id, d12, 0.0),
        Anchor(positive_y_id, x3, y3),
    )


class LiveAnchorMapTracker:
    """Filter pair ranges and maintain one coherent relative anchor-map version."""

    def __init__(
        self,
        configured_anchors: Sequence[Anchor],
        *,
        stale_after_s: float = 5.0,
        median_window: int = 5,
        minimum_samples_per_pair: int = 3,
        movement_threshold_m: float = 0.25,
        movement_confirmation_sets: int = 3,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not configured_anchors:
            raise ValueError("at least one configured anchor is required")
        if stale_after_s <= 0.0 or median_window <= 0:
            raise ValueError("freshness and filter window must be positive")
        if minimum_samples_per_pair <= 0 or movement_confirmation_sets <= 0:
            raise ValueError("sample and confirmation counts must be positive")
        if minimum_samples_per_pair > median_window:
            raise ValueError("minimum samples cannot exceed the median window")
        if movement_threshold_m <= 0.0:
            raise ValueError("movement threshold must be positive")

        self._configured_anchors = tuple(configured_anchors)
        self._survey_ids = tuple(anchor.anchor_id for anchor in configured_anchors[:3])
        self._configured_ids = {anchor.anchor_id for anchor in configured_anchors}
        self._required_pairs = (
            {
                _pair_key(self._survey_ids[0], self._survey_ids[1]),
                _pair_key(self._survey_ids[0], self._survey_ids[2]),
                _pair_key(self._survey_ids[1], self._survey_ids[2]),
            }
            if len(self._survey_ids) == 3
            else set()
        )
        self._stale_after_s = stale_after_s
        self._minimum_samples_per_pair = minimum_samples_per_pair
        self._movement_threshold_m = movement_threshold_m
        self._movement_confirmation_sets = movement_confirmation_sets
        self._clock = clock
        self._windows: dict[tuple[str, str], deque[float]] = {
            pair: deque(maxlen=median_window) for pair in self._required_pairs
        }
        self._latest: dict[tuple[str, str], _PairObservation] = {}
        self._updated_pairs: set[tuple[str, str]] = set()
        self._anchors: tuple[Anchor, ...] | None = None
        self._map_version = 0
        self._pending_anchors: tuple[Anchor, ...] | None = None
        self._pending_count = 0
        self._last_error: str | None = None

    @property
    def anchors(self) -> tuple[Anchor, ...]:
        return self._anchors or self._configured_anchors

    @property
    def map_version(self) -> int:
        return self._map_version

    def observe(self, event: IngestedMeasurement) -> bool:
        """Observe a raw pair result; return true only when a map is committed."""
        measurement = event.measurement
        if not isinstance(measurement, UwbPairRangeMeasurement):
            return False

        key = _pair_key(measurement.node_id, measurement.peer_id)
        accepted = (
            measurement.valid
            and measurement.node_id != measurement.peer_id
            and measurement.node_id in self._configured_ids
            and measurement.peer_id in self._configured_ids
            and key in self._required_pairs
            and 0.05 <= measurement.range_m <= 100.0
        )
        self._latest[key] = _PairObservation(
            measurement=measurement,
            arrival_time_s=event.arrival_time_s,
            accepted=accepted,
        )
        if not accepted:
            self._last_error = "rejected invalid or unsupported pair range"
            return False

        self._windows[key].append(measurement.range_m)
        self._updated_pairs.add(key)
        if self._updated_pairs != self._required_pairs:
            return False
        self._updated_pairs.clear()
        return self._consider_complete_set(event.arrival_time_s)

    def _consider_complete_set(self, now_s: float) -> bool:
        if any(
            len(self._windows[pair]) < self._minimum_samples_per_pair
            for pair in self._required_pairs
        ):
            return False
        if any(
            pair not in self._latest
            or now_s - self._latest[pair].arrival_time_s > self._stale_after_s
            for pair in self._required_pairs
        ):
            self._last_error = "pair ranges are stale"
            return False

        filtered = {
            pair: statistics.median(self._windows[pair])
            for pair in self._required_pairs
        }
        try:
            candidate = solve_three_anchor_map(self._survey_ids, filtered)
        except ValueError as exc:
            self._last_error = str(exc)
            return False

        self._last_error = None
        if self._anchors is None:
            self._commit(candidate)
            return True

        displacement = max(
            math.hypot(new.x_m - old.x_m, new.y_m - old.y_m)
            for old, new in zip(self._anchors[:3], candidate, strict=True)
        )
        if displacement < self._movement_threshold_m:
            self._pending_anchors = None
            self._pending_count = 0
            return False

        if self._pending_anchors is None or self._map_distance(
            self._pending_anchors, candidate
        ) > self._movement_threshold_m / 2.0:
            self._pending_anchors = candidate
            self._pending_count = 1
            return False

        self._pending_anchors = candidate
        self._pending_count += 1
        if self._pending_count < self._movement_confirmation_sets:
            return False
        self._commit(candidate)
        return True

    def _commit(self, anchors: tuple[Anchor, ...]) -> None:
        # Extra anchors need three surveyed constraints of their own. Exclude
        # them from a relative map rather than mixing old fixed-frame points.
        self._anchors = anchors
        self._map_version += 1
        self._pending_anchors = None
        self._pending_count = 0

    @staticmethod
    def _map_distance(first: Sequence[Anchor], second: Sequence[Anchor]) -> float:
        return max(
            math.hypot(right.x_m - left.x_m, right.y_m - left.y_m)
            for left, right in zip(first, second, strict=True)
        )

    def snapshot(self, now_s: float | None = None) -> dict[str, object]:
        current_time_s = self._clock() if now_s is None else now_s
        all_fresh = bool(self._anchors) and all(
            pair in self._latest
            and self._latest[pair].accepted
            and 0.0
            <= current_time_s - self._latest[pair].arrival_time_s
            <= self._stale_after_s
            for pair in self._required_pairs
        )
        status = (
            "unavailable"
            if len(self._survey_ids) < 3
            else "ready"
            if all_fresh
            else "degraded"
            if self._anchors
            else "surveying"
        )

        links: list[dict[str, object]] = []
        for pair in sorted(self._required_pairs):
            observed = self._latest.get(pair)
            if observed is None:
                continue
            measurement = observed.measurement
            links.append(
                {
                    "initiator_id": measurement.node_id,
                    "responder_id": measurement.peer_id,
                    "raw_range_m": measurement.range_m,
                    "timestamp_us": measurement.timestamp_us,
                    "sequence_number": measurement.sequence_number,
                    "valid": measurement.valid,
                    "filtered_range_m": (
                        statistics.median(self._windows[pair])
                        if self._windows[pair]
                        else None
                    ),
                    "accepted": observed.accepted,
                    "age_s": current_time_s - observed.arrival_time_s,
                    "rssi_gap_db": measurement.rssi_gap_db,
                    "rssi_dbm": measurement.rssi_dbm,
                }
            )

        return {
            "source": "live",
            "status": status,
            "map_version": self._map_version,
            "frame": (
                f"{self._survey_ids[0]}_origin_{self._survey_ids[1]}_positive_x"
                if len(self._survey_ids) >= 2
                else "unavailable"
            ),
            "reference_anchor_ids": list(self._survey_ids),
            "anchors": [anchor.__dict__ for anchor in self.anchors],
            "links": links,
            "last_error": self._last_error,
        }
