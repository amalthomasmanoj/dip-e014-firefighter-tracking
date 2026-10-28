from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from backend.models.measurements import ImuMeasurement, Measurement

RESPONDERS_CONFIG_ENV_VAR = "E014_RESPONDERS_CONFIG"
IDENTITY_ROTATION = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
RotationMatrix = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


@dataclass(frozen=True)
class ResponderConfig:
    responder_id: str
    uwb_node_id: str
    imu_node_id: str
    imu_sensor_to_body: RotationMatrix = IDENTITY_ROTATION


def _rotation_matrix(value: object, responder_id: str) -> RotationMatrix:
    if not isinstance(value, Sequence) or isinstance(value, str) or len(value) != 3:
        raise ValueError(f"responder {responder_id!r} transform must have three rows")
    rows: list[tuple[float, float, float]] = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(row, str) or len(row) != 3:
            raise ValueError(f"responder {responder_id!r} transform rows must have three values")
        decoded: list[float] = []
        for item in row:
            if not isinstance(item, int | float) or isinstance(item, bool) or not math.isfinite(item):
                raise ValueError(f"responder {responder_id!r} transform values must be finite")
            decoded.append(float(item))
        rows.append(tuple(decoded))  # type: ignore[arg-type]

    for index, row in enumerate(rows):
        if not math.isclose(sum(item * item for item in row), 1.0, abs_tol=1e-6):
            raise ValueError(f"responder {responder_id!r} transform row {index} is not unit length")
    for left in range(3):
        for right in range(left + 1, 3):
            if not math.isclose(
                sum(rows[left][axis] * rows[right][axis] for axis in range(3)),
                0.0,
                abs_tol=1e-6,
            ):
                raise ValueError(f"responder {responder_id!r} transform rows are not orthogonal")
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    if not math.isclose(determinant, 1.0, abs_tol=1e-6):
        raise ValueError(f"responder {responder_id!r} transform must be right-handed")
    return tuple(rows)  # type: ignore[return-value]


def load_responders(path: str | Path) -> tuple[ResponderConfig, ...]:
    config_path = Path(path)
    try:
        decoded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read responder config {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in responder config {config_path}: {exc}") from exc
    if not isinstance(decoded, Mapping):
        raise TypeError("responder config must be a mapping")
    entries = decoded.get("responders")
    if not isinstance(entries, list) or not entries:
        raise ValueError("responder config field 'responders' must be a non-empty list")

    responders: list[ResponderConfig] = []
    logical_ids: set[str] = set()
    physical_owners: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise TypeError(f"responder entry {index} must be a mapping")
        fields: dict[str, str] = {}
        for name in ("responder_id", "uwb_node_id", "imu_node_id"):
            value = entry.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"responder entry {index} has an invalid {name}")
            fields[name] = value.strip()
        if fields["responder_id"] in logical_ids:
            raise ValueError(f"duplicate responder_id {fields['responder_id']!r}")
        for name in ("uwb_node_id", "imu_node_id"):
            node_id = fields[name]
            owner = physical_owners.get(node_id)
            if owner is not None and owner != fields["responder_id"]:
                raise ValueError(f"physical node {node_id!r} is assigned more than once")
            physical_owners[node_id] = fields["responder_id"]
        logical_ids.add(fields["responder_id"])
        responders.append(
            ResponderConfig(
                **fields,
                imu_sensor_to_body=_rotation_matrix(
                    entry.get("imu_sensor_to_body", IDENTITY_ROTATION),
                    fields["responder_id"],
                ),
            )
        )
    return tuple(responders)


def responders_from_env(env: Mapping[str, str] | None = None) -> tuple[ResponderConfig, ...]:
    environ = os.environ if env is None else env
    path = environ.get(RESPONDERS_CONFIG_ENV_VAR)
    return load_responders(path) if path else ()


def _rotate(vector: tuple[float, float, float], matrix: RotationMatrix) -> tuple[float, float, float]:
    return tuple(sum(row[index] * vector[index] for index in range(3)) for row in matrix)  # type: ignore[return-value]


def measurement_for_responder(
    measurement: Measurement,
    config: ResponderConfig,
) -> Measurement:
    if isinstance(measurement, ImuMeasurement):
        accel = _rotate(
            (measurement.ax_mps2, measurement.ay_mps2, measurement.az_mps2),
            config.imu_sensor_to_body,
        )
        gyro = _rotate(
            (measurement.gx_radps, measurement.gy_radps, measurement.gz_radps),
            config.imu_sensor_to_body,
        )
        return replace(
            measurement,
            node_id=config.responder_id,
            ax_mps2=accel[0],
            ay_mps2=accel[1],
            az_mps2=accel[2],
            gx_radps=gyro[0],
            gy_radps=gyro[1],
            gz_radps=gyro[2],
        )
    return replace(measurement, node_id=config.responder_id)


class ResponderRegistry:
    def __init__(self, responders: Sequence[ResponderConfig] = ()) -> None:
        self._by_node: dict[str, ResponderConfig] = {}
        for responder in responders:
            self._by_node[responder.uwb_node_id] = responder
            self._by_node[responder.imu_node_id] = responder

    def resolve(self, measurement: Measurement) -> tuple[str, Measurement]:
        config = self._by_node.get(measurement.node_id)
        if config is None:
            return measurement.node_id, measurement
        return config.responder_id, measurement_for_responder(measurement, config)
