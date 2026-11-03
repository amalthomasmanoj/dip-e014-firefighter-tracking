from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from backend.api.live import LiveUdpStateHub
from backend.api.websocket import state_messages_for_source
from backend.config.responders import ResponderConfig, responders_from_env
from backend.config.source import SourceMode, source_mode_from_env
from backend.heart_rate.monitor import AlertSettings
from backend.heart_rate.receiver import HeartRateReceiver
from backend.simulation.world import SimulationWorld
from backend.uwb.anchor_map import LiveAnchorMapTracker
from backend.uwb.anchors import (
    Anchor,
    anchors_are_explicitly_configured,
    anchors_from_env,
)
from backend.uwb.live_ranges import LiveUwbRangeTracker


class SimulationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["firefighter", "anchor"]
    node_id: str
    action: Literal["move", "toggle_lying"] = "move"
    dx_m: float = Field(default=0.0, ge=-0.2, le=0.2, allow_inf_nan=False)
    dy_m: float = Field(default=0.0, ge=-0.2, le=0.2, allow_inf_nan=False)


class HeadingAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading_rad: float = Field(allow_inf_nan=False)


def create_app(
    source_mode: SourceMode | None = None,
    anchors: Sequence[Anchor] | None = None,
    responders: Sequence[ResponderConfig] | None = None,
) -> FastAPI:
    active_source_mode = source_mode or source_mode_from_env()
    configured_anchors = tuple(anchors) if anchors is not None else anchors_from_env()
    has_explicit_anchor_map = anchors is not None or anchors_are_explicitly_configured()
    heart_rate = HeartRateReceiver.from_env()
    live_uwb_ranges = LiveUwbRangeTracker()
    live_anchor_map = LiveAnchorMapTracker(
        configured_anchors,
        use_configured_fallback=has_explicit_anchor_map,
    )
    configured_responders = (
        tuple(responders) if responders is not None else responders_from_env()
    )
    live_hub = LiveUdpStateHub(
        live_uwb_ranges,
        live_anchor_map.anchors,
        live_anchor_map,
        configured_responders,
    )
    simulation = (
        SimulationWorld(configured_anchors) if active_source_mode is SourceMode.SIMULATION else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if active_source_mode is SourceMode.UDP:
            await live_hub.start()
        if simulation is not None:
            await simulation.start()
        await heart_rate.start()
        try:
            yield
        finally:
            await heart_rate.stop()
            await live_hub.stop()
            if simulation is not None:
                await simulation.stop()

    app = FastAPI(title="E014 Firefighter Tracking Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost",
            "https://localhost",
            "capacitor://localhost",
        ],
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
            if command.action == "toggle_lying":
                if command.kind != "firefighter":
                    raise ValueError("only firefighters can change lying posture")
                simulation.toggle_lying(command.node_id)
            else:
                simulation.move(command.kind, command.node_id, command.dx_m, command.dy_m)
        except KeyError as exc:
            raise HTTPException(404, "unknown simulation node") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"accepted": True}

    @app.post("/heart-rate/settings")
    async def heart_rate_settings(settings: AlertSettings) -> dict:
        heart_rate.monitor.configure(settings)
        return heart_rate.monitor.snapshot()

    @app.post("/heart-rate/alerts/{event_id}/acknowledge")
    async def acknowledge_heart_rate_alert(event_id: int) -> dict:
        if not heart_rate.monitor.acknowledge(event_id):
            raise HTTPException(404, "unknown heart-rate alert")
        return heart_rate.monitor.snapshot()

    @app.get("/heart-rate")
    async def heart_rate_snapshot() -> dict:
        return heart_rate.snapshot()

    @app.get("/uwb/ranges")
    def uwb_ranges(tag_node_id: str | None = None) -> dict[str, object]:
        physical_node_id = (
            live_hub.uwb_node_id(tag_node_id) if tag_node_id is not None else None
        )
        return live_uwb_ranges.snapshot(node_id=physical_node_id)

    @app.get("/uwb/anchor-map")
    def uwb_anchor_map() -> dict[str, object]:
        return live_anchor_map.snapshot()

    @app.get("/responders/{responder_id}/sensor-status")
    def responder_sensor_status(responder_id: str) -> dict[str, object]:
        return live_hub.sensor_status(responder_id)

    @app.post("/responders/{responder_id}/heading-alignment")
    def align_heading(responder_id: str, alignment: HeadingAlignment) -> dict[str, object]:
        try:
            live_hub.align_heading(responder_id, alignment.heading_rad)
        except KeyError as exc:
            raise HTTPException(404, "responder has not produced a measurement") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"accepted": True, "responder_id": responder_id, "heading_rad": alignment.heading_rad}

    @app.post("/responders/{responder_id}/imu-mount-calibration")
    def calibrate_imu_mount(responder_id: str) -> dict[str, object]:
        if active_source_mode is not SourceMode.UDP:
            raise HTTPException(409, "IMU mount calibration requires real sensors")
        try:
            calibration = live_hub.calibrate_imu_mount(responder_id)
        except KeyError as exc:
            raise HTTPException(404, "unknown configured responder") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "accepted": True,
            "responder_id": responder_id,
            "imu_sensor_to_body": calibration.sensor_to_body,
            "sample_count": calibration.sample_count,
            "mean_accel_mps2": calibration.mean_accel_mps2,
            "accel_rms_deviation_mps2": calibration.accel_rms_deviation_mps2,
            "mean_gyro_norm_radps": calibration.mean_gyro_norm_radps,
        }

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

    ui_dist_value = os.environ.get("E014_UI_DIST")
    ui_dist = Path(ui_dist_value) if ui_dist_value else Path(__file__).parents[2] / "ui/web/dist"
    if ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")

    return app


app = create_app()
