from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_packet_examples_validate_against_schema() -> None:
    schema = load_json(CONTRACTS / "packet_schema.json")
    for example in [
        CONTRACTS / "examples" / "imu_packet.json",
        CONTRACTS / "examples" / "uwb_range_packet.json",
    ]:
        jsonschema.validate(load_json(example), schema)


def test_estimated_state_example_validates_against_schema() -> None:
    schema = load_json(CONTRACTS / "estimated_state.schema.json")
    example = load_json(CONTRACTS / "examples" / "estimated_state.json")
    jsonschema.validate(example, schema)


def test_websocket_schema_accepts_estimated_state_message() -> None:
    estimated_schema = load_json(CONTRACTS / "estimated_state.schema.json")
    websocket_schema = load_json(CONTRACTS / "websocket_state.schema.json")
    registry = Registry().with_resource(
        "estimated_state.schema.json",
        Resource.from_contents(estimated_schema),
    )
    validator = jsonschema.Draft202012Validator(websocket_schema, registry=registry)
    validator.validate(
        {
            "type": "estimated_state",
            "source": "simulation",
            "state": load_json(CONTRACTS / "examples" / "estimated_state.json"),
        }
    )

