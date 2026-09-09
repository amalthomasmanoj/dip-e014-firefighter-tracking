from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.api.websocket import state_messages_for_source
from backend.config.source import SourceMode, source_mode_from_env
from backend.uwb.anchors import DEFAULT_ANCHORS


def create_app(source_mode: SourceMode | None = None) -> FastAPI:
    active_source_mode = source_mode or source_mode_from_env()
    app = FastAPI(title="E014 Firefighter Tracking Backend")

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

    @app.websocket("/ws/state")
    async def state_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            async for message in state_messages_for_source(active_source_mode):
                await websocket.send_text(message)
        except NotImplementedError as exc:
            await websocket.close(code=1013, reason=str(exc))
        except WebSocketDisconnect:
            return

    return app


app = create_app()
