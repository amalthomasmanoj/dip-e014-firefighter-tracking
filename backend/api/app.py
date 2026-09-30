from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.live import LiveUdpStateHub
from backend.api.websocket import state_messages_for_source
from backend.config.source import SourceMode, source_mode_from_env
from backend.uwb.anchors import DEFAULT_ANCHORS
from backend.uwb.live_ranges import LiveUwbRangeTracker


def create_app(source_mode: SourceMode | None = None) -> FastAPI:
    active_source_mode = source_mode or source_mode_from_env()
    live_uwb_ranges = LiveUwbRangeTracker()
    live_hub = LiveUdpStateHub(live_uwb_ranges)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if active_source_mode is SourceMode.UDP:
            await live_hub.start()
        try:
            yield
        finally:
            await live_hub.stop()

    app = FastAPI(title="E014 Firefighter Tracking Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.live_uwb_ranges = live_uwb_ranges
    app.state.live_hub = live_hub

    @app.get("/health")
    def health() -> dict[str, str]:
        source_status = (
            "available" if active_source_mode.is_stream_available else "not_implemented"
        )
        return {
            "status": "ok",
            "source": active_source_mode.value,
            "source_status": source_status,
        }

    @app.get("/anchors")
    def anchors() -> list[dict[str, float | str]]:
        return [anchor.__dict__ for anchor in DEFAULT_ANCHORS]

    @app.get("/uwb/ranges")
    def uwb_ranges() -> dict[str, object]:
        return live_uwb_ranges.snapshot()

    @app.websocket("/ws/state")
    async def state_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            messages = (
                live_hub.messages()
                if active_source_mode is SourceMode.UDP
                else state_messages_for_source(active_source_mode)
            )
            async for message in messages:
                await websocket.send_text(message)
        except NotImplementedError as exc:
            await websocket.close(code=1013, reason=str(exc))
        except WebSocketDisconnect:
            return

    return app


app = create_app()
