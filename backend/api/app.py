from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from backend.api.live import LiveUdpStateHub
from backend.api.websocket import state_messages_for_source
from backend.config.source import SourceMode, source_mode_from_env
from backend.simulation.world import SimulationWorld
from backend.uwb.anchor_map import LiveAnchorMapTracker
from backend.uwb.anchors import Anchor, anchors_from_env
from backend.uwb.live_ranges import LiveUwbRangeTracker


class SimulationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["firefighter", "anchor"]
    node_id: str
    action: Literal["move", "toggle_crouch"] = "move"
    dx_m: float = Field(default=0.0, ge=-0.2, le=0.2, allow_inf_nan=False)
    dy_m: float = Field(default=0.0, ge=-0.2, le=0.2, allow_inf_nan=False)


def create_app(
    source_mode: SourceMode | None = None,
    anchors: Sequence[Anchor] | None = None,
) -> FastAPI:
    active_source_mode = source_mode or source_mode_from_env()
    configured_anchors = tuple(anchors) if anchors is not None else anchors_from_env()
    live_uwb_ranges = LiveUwbRangeTracker()
    live_anchor_map = LiveAnchorMapTracker(configured_anchors)
    live_hub = LiveUdpStateHub(live_uwb_ranges, configured_anchors, live_anchor_map)
    simulation = (
        SimulationWorld(configured_anchors) if active_source_mode is SourceMode.SIMULATION else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if active_source_mode is SourceMode.UDP:
            await live_hub.start()
        if simulation is not None:
            await simulation.start()
        try:
            yield
        finally:
            await live_hub.stop()
            if simulation is not None:
                await simulation.stop()

    app = FastAPI(title="E014 Firefighter Tracking Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.live_uwb_ranges = live_uwb_ranges
    app.state.live_hub = live_hub
    app.state.live_anchor_map = live_anchor_map
    app.state.simulation = simulation

    @app.get("/health")
    def health() -> dict[str, str]:
        source_status = "available" if active_source_mode.is_stream_available else "not_implemented"
        return {
            "status": "ok",
            "source": active_source_mode.value,
            "source_status": source_status,
        }

    @app.get("/anchors")
    def anchors() -> list[dict[str, float | str]]:
        current = simulation.anchors if simulation is not None else live_anchor_map.anchors
        return [anchor.__dict__ for anchor in current]

    @app.get("/simulation")
    async def simulation_snapshot() -> dict:
        if simulation is None:
            raise HTTPException(409, "simulation controls require E014_SOURCE=simulation")
        return simulation.snapshot()

    @app.post("/simulation/command")
    async def simulation_command(command: SimulationCommand) -> dict:
        if simulation is None:
            raise HTTPException(409, "simulation controls require E014_SOURCE=simulation")
        try:
            if command.action == "toggle_crouch":
                if command.kind != "firefighter":
                    raise ValueError("only firefighters can crouch")
                simulation.toggle_crouch(command.node_id)
            else:
                simulation.move(command.kind, command.node_id, command.dx_m, command.dy_m)
        except KeyError as exc:
            raise HTTPException(404, "unknown simulation node") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"accepted": True}

    @app.get("/uwb/ranges")
    def uwb_ranges(tag_node_id: str | None = None) -> dict[str, object]:
        return live_uwb_ranges.snapshot(node_id=tag_node_id)

    @app.get("/uwb/anchor-map")
    def uwb_anchor_map() -> dict[str, object]:
        return live_anchor_map.snapshot()

    @app.websocket("/ws/state")
    async def state_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            if active_source_mode is SourceMode.UDP:
                messages = live_hub.messages()
            elif simulation is not None:
                messages = simulation.primary_messages()
            else:
                messages = state_messages_for_source(active_source_mode)
            async for message in messages:
                await websocket.send_text(message)
        except NotImplementedError as exc:
            await websocket.close(code=1013, reason=str(exc))
        except WebSocketDisconnect:
            return

    return app


app = create_app()
