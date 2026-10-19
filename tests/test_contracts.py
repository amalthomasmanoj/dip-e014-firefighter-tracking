from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.ingestion.parser import parse_packet
from tools.fake_data.imu_scenario import imu_packet_stream


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



def test_estimated_state_schema_accepts_lying_down_posture() -> None:
    schema = load_json(CONTRACTS / "estimated_state.schema.json")
    example = load_json(CONTRACTS / "examples" / "estimated_state.json")
    example["activity"] = {
        "posture": "lying_down",
        "motion": "stationary",
        "confidence": 0.8,
    }

    jsonschema.validate(example, schema)


def test_estimated_state_schema_still_rejects_unknown_posture() -> None:
    schema = load_json(CONTRACTS / "estimated_state.schema.json")
    example = load_json(CONTRACTS / "examples" / "estimated_state.json")
    example["activity"] = {"posture": "falling", "motion": "stationary", "confidence": 0.8}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(example, schema)


def test_published_states_validate_against_the_state_contract() -> None:
    """Every scenario's emitted state must satisfy the shared contract."""
    schema = load_json(CONTRACTS / "estimated_state.schema.json")
    estimator = DemoSensorEstimator()

    for packet in imu_packet_stream(scenario="full"):
        state = estimator.update(parse_packet(packet))
        assert state is not None
        jsonschema.validate(state.to_dict(), schema)
