from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

ANCHORS_CONFIG_ENV_VAR = "E014_ANCHORS_CONFIG"


@dataclass(frozen=True)
class Anchor:
    anchor_id: str
    x_m: float
    y_m: float
    z_m: float = 0.0


DEFAULT_ANCHORS = (
    Anchor("A1", 0.0, 0.0, 0.0),
    Anchor("A2", 8.0, 0.0, 0.0),
    Anchor("A3", 0.0, 6.0, 0.0),
)


def load_anchors(path: str | Path) -> tuple[Anchor, ...]:
    """Load measured anchor coordinates without changing the packet contract."""
    config_path = Path(path)
    try:
        decoded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read anchor config {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in anchor config {config_path}: {exc}") from exc

    if not isinstance(decoded, Mapping):
        raise TypeError("anchor config must be a mapping with an 'anchors' list")
    entries = decoded.get("anchors")
    if not isinstance(entries, list) or not entries:
        raise ValueError("anchor config field 'anchors' must be a non-empty list")

    anchors: list[Anchor] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise TypeError(f"anchor entry {index} must be a mapping")
        anchor_id = entry.get("anchor_id")
        if not isinstance(anchor_id, str) or not anchor_id.strip():
            raise ValueError(f"anchor entry {index} has an invalid anchor_id")
        anchor_id = anchor_id.strip()
        if anchor_id in seen_ids:
            raise ValueError(f"duplicate anchor_id {anchor_id!r}")

        coordinates: dict[str, float] = {}
        for field in ("x_m", "y_m", "z_m"):
            raw_value = entry.get(field, 0.0 if field == "z_m" else None)
            if (
                not isinstance(raw_value, int | float)
                or isinstance(raw_value, bool)
                or not math.isfinite(float(raw_value))
            ):
                raise ValueError(f"anchor {anchor_id!r} field {field!r} must be finite")
            coordinates[field] = float(raw_value)

        anchors.append(Anchor(anchor_id=anchor_id, **coordinates))
        seen_ids.add(anchor_id)

    return tuple(anchors)


def anchors_from_env(env: Mapping[str, str] | None = None) -> tuple[Anchor, ...]:
    environ = os.environ if env is None else env
    config_path = environ.get(ANCHORS_CONFIG_ENV_VAR)
    return load_anchors(config_path) if config_path else DEFAULT_ANCHORS
