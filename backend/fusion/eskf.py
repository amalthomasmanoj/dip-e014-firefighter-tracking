from __future__ import annotations

from backend.models.state import EstimatedState


class EskfPlaceholder:
    """Explicit placeholder so bootstrap code does not pretend fusion is complete."""

    def update(self, state: EstimatedState) -> EstimatedState:
        return state

