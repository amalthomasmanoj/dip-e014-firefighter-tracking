from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import jsonschema
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.api.app import SimulationCommand, create_app
from backend.config.source import SourceMode
from backend.simulation.world import SimulationWorld
from backend.uwb.anchors import DEFAULT_ANCHORS, Anchor


def test_two_firefighters_have_independent_positions_sequences_and_estimates():
    world = SimulationWorld(DEFAULT_ANCHORS)
    before = world.snapshot()
    first, second = before["firefighters"]
    assert first["state"]["position_m"]["x"] == pytest.approx(1)
    assert second["state"]["position_m"]["x"] == pytest.approx(5)
    for _ in range(5):
        world.move("firefighter", "sim_tag_10", 0.2, 0)
        world.step()
    for _ in range(30):
        world.step()
    after = world.snapshot()
    assert after["firefighters"][0]["state"]["position_m"]["x"] == pytest.approx(2, abs=0.1)
    assert after["firefighters"][1]["state"]["position_m"] == second["state"]["position_m"]
    for node_id in world.firefighters:
        packets = [p for p in after["raw_packets"] if p["node_id"] == node_id]
        sequences = [p["sequence_number"] for p in packets]
        assert sequences == list(range(sequences[0], sequences[0] + len(sequences)))
    # Earlier raw measurements remain raw and unchanged after filter updates.
    assert before["raw_packets"][1]["data"]["range_m"] == pytest.approx(math.sqrt(2))


def test_every_anchor_pair_exchanges_repeatedly_while_tags_are_stationary():
    world = SimulationWorld((*DEFAULT_ANCHORS, Anchor("A4", 8, 6)))
    before = world.snapshot()
    after = world.step()
    assert len(after["anchor_links"]) == 6
    for old, new in zip(before["anchor_links"], after["anchor_links"], strict=True):
        assert new["sequence_number"] == old["sequence_number"] + 1
        assert new["timestamp_us"] > old["timestamp_us"]
        assert new["raw_range_m"] == old["raw_range_m"]
        assert new["valid"]


@pytest.mark.parametrize("anchor_id", ["A1", "A2", "A3"])
def test_moving_any_anchor_preserves_fixed_world_tag_positions(anchor_id):
    world = SimulationWorld(DEFAULT_ANCHORS)
    initial = world.snapshot()
    for _ in range(6):
        world.move("anchor", anchor_id, 0.2, 0.1)
        snapshot = world.step()
        assert snapshot["map_version"] > initial["map_version"]
        assert snapshot["frame"] == "fixed_world"
        for original, updated in zip(
            initial["firefighters"], snapshot["firefighters"], strict=True
        ):
            for axis in ("x", "y"):
                assert updated["state"]["position_m"][axis] == pytest.approx(
                    original["state"]["position_m"][axis],
                    abs=0.01,
                )
    assert snapshot["anchor_links"] != initial["anchor_links"]
    assert snapshot["raw_packets"][1:] != initial["raw_packets"][1:]


def test_collinear_geometry_is_unresolved_then_recovers():
    world = SimulationWorld((Anchor("A1", 0, 0), Anchor("A2", 8, 0), Anchor("A3", 0, 0.2)))
    world.move("anchor", "A3", 0, -0.2)
    snapshot = world.step()
    assert not snapshot["geometry_valid"]
    assert all(tag["state"] is None for tag in snapshot["firefighters"])
    assert len(snapshot["anchor_links"]) == 3
    world.move("anchor", "A3", 0, 0.2)
    assert all(tag["state"] is not None for tag in world.step()["firefighters"])


def test_simulation_packets_and_states_keep_existing_contracts():
    snapshot = SimulationWorld(DEFAULT_ANCHORS).snapshot()
    schema = json.loads(Path("contracts/packet_schema.json").read_text())
    for packet in snapshot["raw_packets"]:
        jsonschema.validate(packet, schema)
    state_schema = json.loads(Path("contracts/estimated_state.schema.json").read_text())
    for tag in snapshot["firefighters"]:
        jsonschema.validate(tag["state"], state_schema)


def route(app, path):
    return next(r.endpoint for r in app.routes if getattr(r, "path", None) == path)


@pytest.mark.parametrize("mode", [SourceMode.UDP, SourceMode.REPLAY])
def test_simulation_endpoints_reject_non_simulation_sources(mode):
    app = create_app(source_mode=mode)
    with pytest.raises(HTTPException) as error:
        asyncio.run(route(app, "/simulation")())
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            route(app, "/simulation/command")(
                SimulationCommand(kind="anchor", node_id="A1", dx_m=0.2),
            )
        )
    assert error.value.status_code == 409
    assert route(app, "/anchors")()[0]["x_m"] == 0


def test_simulation_commands_and_shared_lifecycle():
    async def check():
        app = create_app(source_mode=SourceMode.SIMULATION)
        async with app.router.lifespan_context(app):
            snapshot = route(app, "/simulation")
            before = await snapshot()
            await route(app, "/simulation/command")(
                SimulationCommand(kind="anchor", node_id="A3", dx_m=0.2),
            )
            await asyncio.sleep(0.15)
            after = await snapshot()
            assert after["timestamp_us"] > before["timestamp_us"]
            assert after["anchors"][2]["x_m"] == 0.2
            assert route(app, "/anchors")() == after["anchors"]
            stream = app.state.simulation.primary_messages()
            message = json.loads(await anext(stream))
            assert message["state"] == after["firefighters"][0]["state"]
            assert set(message) == {"type", "source", "state"}
            await stream.aclose()
            assert await snapshot() == after  # Reading does not advance the world.
        assert app.state.simulation._task is None

    asyncio.run(check())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1.0, -0.21])
def test_invalid_movement_is_rejected(value):
    with pytest.raises(ValidationError):
        SimulationCommand(kind="anchor", node_id="A1", dx_m=value)


def test_unknown_nodes_and_invalid_actions_do_not_mutate_world():
    async def check():
        app = create_app(source_mode=SourceMode.SIMULATION)
        command = route(app, "/simulation/command")
        for request, status in [
            (SimulationCommand(kind="anchor", node_id="missing"), 404),
            (SimulationCommand(kind="firefighter", node_id="missing"), 404),
            (SimulationCommand(kind="anchor", node_id="A1", action="toggle_crouch"), 422),
        ]:
            with pytest.raises(HTTPException) as error:
                await command(request)
            assert error.value.status_code == status
        assert app.state.simulation.map_version == 1

    asyncio.run(check())
