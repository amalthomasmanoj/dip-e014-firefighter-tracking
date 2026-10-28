from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Callable

from backend.ingestion.events import IngestedMeasurement
from backend.ingestion.parser import parse_packet
from backend.ingestion.sequencing import SequenceTracker
from backend.ingestion.udp_receiver import receive_udp_packets

logger = logging.getLogger(__name__)


def ingest_datagram(
    payload: bytes,
    tracker: SequenceTracker,
    arrival_time_s: float,
) -> IngestedMeasurement:
    measurement = parse_packet(payload)
    sequence_status = tracker.observe(measurement.node_id, measurement.sequence_number)
    return IngestedMeasurement(
        measurement=measurement,
        sequence_status=sequence_status,
        arrival_time_s=arrival_time_s,
        raw_payload=payload,
    )


async def ingest_datagrams(
    payloads: AsyncIterator[bytes],
    tracker: SequenceTracker | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> AsyncIterator[IngestedMeasurement]:
    """Yield valid measurements without letting one bad datagram kill the stream."""
    active_tracker = tracker or SequenceTracker()
    rejected = 0
    async for payload in payloads:
        try:
            event = ingest_datagram(
                payload=payload,
                tracker=active_tracker,
                arrival_time_s=clock(),
            )
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            rejected += 1
            if rejected <= 5 or rejected % 100 == 0:
                logger.warning(
                    "rejected UDP datagram #%d: %s; payload=%.200r",
                    rejected,
                    exc,
                    payload,
                )
            continue
        yield event


async def udp_measurement_events(
    host: str = "0.0.0.0",
    port: int = 9000,
    tracker: SequenceTracker | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> AsyncIterator[IngestedMeasurement]:
    async for event in ingest_datagrams(
        receive_udp_packets(host=host, port=port),
        tracker=tracker,
        clock=clock,
    ):
        yield event
