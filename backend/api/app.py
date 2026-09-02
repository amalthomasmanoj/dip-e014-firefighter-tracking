from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.api.websocket import fake_state_messages
from backend.uwb.anchors import DEFAULT_ANCHORS


app = FastAPI(title="E014 Firefighter Tracking Backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "source": "simulation"}


@app.get("/anchors")
def anchors() -> list[dict[str, float | str]]:
    return [anchor.__dict__ for anchor in DEFAULT_ANCHORS]


@app.websocket("/ws/state")
async def state_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for message in fake_state_messages():
            await websocket.send_text(message)
    except WebSocketDisconnect:
        return

