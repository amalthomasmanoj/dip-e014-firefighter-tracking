from __future__ import annotations

from backend.models.state import EstimatedState


def propagate_placeholder(state: EstimatedState) -> EstimatedState:
    """Placeholder for later INS propagation; returns state unchanged."""
    return state

