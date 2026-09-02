from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SequenceStatus:
    node_id: str
    sequence_number: int
    gap_detected: bool
    out_of_order: bool
    expected_sequence_number: int | None


class SequenceTracker:
    def __init__(self) -> None:
        self._last_by_node: dict[str, int] = {}

    def observe(self, node_id: str, sequence_number: int) -> SequenceStatus:
        last = self._last_by_node.get(node_id)
        expected = None if last is None else last + 1
        out_of_order = last is not None and sequence_number <= last
        gap_detected = last is not None and sequence_number > last + 1

        if not out_of_order:
            self._last_by_node[node_id] = sequence_number

        return SequenceStatus(
            node_id=node_id,
            sequence_number=sequence_number,
            gap_detected=gap_detected,
            out_of_order=out_of_order,
            expected_sequence_number=expected,
        )

