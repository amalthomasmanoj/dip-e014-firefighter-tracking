from __future__ import annotations

from dataclasses import dataclass

from backend.ingestion.sequencing import SequenceStatus
from backend.models.measurements import Measurement


@dataclass(frozen=True)
class IngestedMeasurement:
    measurement: Measurement
    sequence_status: SequenceStatus
    arrival_time_s: float
    raw_payload: bytes
