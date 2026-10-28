from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass
from itertools import combinations

from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.ingestion.pipeline import ingest_datagram
from backend.ingestion.sequencing import SequenceTracker
from backend.uwb.anchors import Anchor
from backend.uwb.trilateration import trilaterate_2d


@dataclass
class SimulatedFirefighter:
    node_id: str
    label: str
    x_m: float
    y_m: float
    lying_down: bool = False
    moving_until_us: int = 0
    sequence_number: int = 0


class SimulationWorld:
    """Shared 10 Hz, planar, ideal-range scenario in a fixed world frame.

    Pair exchanges are synthetic telemetry, NOT a hardware packet format or
    self-survey algorithm. Known coordinates come from the scenario controls.
    Each tag owns its own parser sequence state and estimator.
    """

    interval_s = 0.1

    def __init__(self, anchors: Sequence[Anchor]) -> None:
        self.anchors = tuple(anchors)
        self.map_version = 1
        self.timestamp_us = 0
        self.firefighters = {
            tag.node_id: tag
            for tag in (
                SimulatedFirefighter("sim_tag_10", "Firefighter 1 · tag 10", 1.0, 1.0),
                SimulatedFirefighter("sim_tag_11", "Firefighter 2 · tag 11", 5.0, 3.0),
            )
        }
        self._estimators = {
            node_id: DemoSensorEstimator(anchors=self.anchors, emit_imu_only_state=False)
            for node_id in self.firefighters
        }
        self._trackers = {node_id: SequenceTracker() for node_id in self.firefighters}
        self._task: asyncio.Task[None] | None = None
        self._snapshot: dict = {}
        self.step()

    def move(self, kind: str, node_id: str, dx_m: float, dy_m: float) -> None:
        if not all(math.isfinite(v) and abs(v) <= 0.2 for v in (dx_m, dy_m)):
            raise ValueError("movement must be finite and at most 0.2 m per axis")
        if kind == "firefighter":
            tag = self.firefighters[node_id]
            tag.x_m = max(-0.5, min(8.5, tag.x_m + dx_m))
            tag.y_m = max(-0.5, min(6.5, tag.y_m + dy_m))
            tag.moving_until_us = self.timestamp_us + 300_000
            return
        if kind != "anchor":
            raise ValueError("unknown target kind")
        if node_id not in {a.anchor_id for a in self.anchors}:
            raise KeyError(node_id)
        updated = tuple(
            Anchor(
                a.anchor_id,
                max(-0.5, min(8.5, a.x_m + dx_m)),
                max(-0.5, min(6.5, a.y_m + dy_m)),
                a.z_m,
            )
            if a.anchor_id == node_id
            else a
            for a in self.anchors
        )
        if updated == self.anchors:
            return
        self.anchors = updated
        self.map_version += 1
        for estimator in self._estimators.values():
            estimator.set_anchors(updated)

    def toggle_lying(self, node_id: str) -> None:
        tag = self.firefighters[node_id]
        tag.lying_down = not tag.lying_down

    def step(self) -> dict:
        self.timestamp_us += 100_000
        pairs = [
            {
                "initiator_id": a.anchor_id,
                "responder_id": b.anchor_id,
                "timestamp_us": self.timestamp_us,
                "sequence_number": self.timestamp_us // 100_000,
                "raw_range_m": math.dist((a.x_m, a.y_m, a.z_m), (b.x_m, b.y_m, b.z_m)),
                "valid": True,
            }
            for a, b in combinations(self.anchors, 2)
        ]
        try:
            trilaterate_2d(list(self.anchors), {a.anchor_id: 1.0 for a in self.anchors})
            geometry_valid = True
        except ValueError:
            geometry_valid = False
        responders = []
        raw_packets = []
        for node_id, tag in self.firefighters.items():
            moving = self.timestamp_us < tag.moving_until_us
            data = {
                "ax_mps2": 9.81 if tag.lying_down else (0.5 if moving else 0.0),
                "ay_mps2": 0.0,
                "az_mps2": 0.0 if tag.lying_down else 9.81,
                "gx_radps": 0.0,
                "gy_radps": 0.0,
                "gz_radps": 0.1 if moving else 0.0,
            }
            packets = [("imu", data)]
            for anchor in self.anchors:
                # Planar simulator: current demo estimator consumes horizontal ranges.
                packets.append(
                    (
                        "uwb_range",
                        {
                            "anchor_id": anchor.anchor_id,
                            "range_m": math.hypot(anchor.x_m - tag.x_m, anchor.y_m - tag.y_m),
                            "valid": True,
                            "quality": None,
                        },
                    )
                )
            state = None
            ranges = []
            for offset, (packet_type, packet_data) in enumerate(packets):
                tag.sequence_number += 1
                packet = {
                    "version": 1,
                    "node_id": node_id,
                    "sequence_number": tag.sequence_number,
                    "timestamp_us": self.timestamp_us + offset,
                    "type": packet_type,
                    "data": packet_data,
                }
                raw_packets.append(packet)
                event = ingest_datagram(
                    json.dumps(packet).encode(),
                    self._trackers[node_id],
                    arrival_time_s=packet["timestamp_us"] / 1_000_000,
                )
                estimate = self._estimators[node_id].update(event.measurement)
                if estimate is not None:
                    state = estimate
                if packet_type == "uwb_range":
                    ranges.append(
                        {
                            "anchor_id": packet_data["anchor_id"],
                            "range_m": packet_data["range_m"],
                            "measurement_timestamp_us": packet["timestamp_us"],
                            "age_s": 0.0,
                        }
                    )
            responders.append(
                {
                    "node_id": node_id,
                    "label": tag.label,
                    "state": state.to_dict() if state and geometry_valid else None,
                    "ranges": ranges,
                }
            )
        self._snapshot = {
            "source": "simulation",
            "timestamp_us": self.timestamp_us,
            "map_version": self.map_version,
            "frame": "fixed_world",
            "geometry_valid": geometry_valid,
            "anchors": [asdict(a) for a in self.anchors],
            "firefighters": responders,
            "anchor_links": pairs,
            "raw_packets": raw_packets,
        }
        return self._snapshot

    def snapshot(self) -> dict:
        return self._snapshot

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            self.step()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def primary_messages(self) -> AsyncIterator[str]:
        """Keep the legacy single-state WebSocket shape for tag 10 consumers."""
        previous = -1
        while True:
            snapshot = self.snapshot()
            state = snapshot["firefighters"][0]["state"]
            if state is not None and snapshot["timestamp_us"] != previous:
                previous = snapshot["timestamp_us"]
                yield json.dumps(
                    {"type": "estimated_state", "source": "simulation", "state": state}
                )
            await asyncio.sleep(self.interval_s)
