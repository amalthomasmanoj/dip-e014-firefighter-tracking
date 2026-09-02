from __future__ import annotations

import math

import pytest


def world_to_map(
    position: tuple[float, float],
    *,
    scale: float,
    rotation_rad: float,
    translate: tuple[float, float],
) -> tuple[float, float]:
    if scale == 0 or not all(
        math.isfinite(value)
        for value in [position[0], position[1], scale, rotation_rad, translate[0], translate[1]]
    ):
        raise ValueError("invalid transform")
    c = math.cos(rotation_rad)
    s = math.sin(rotation_rad)
    return (
        scale * (c * position[0] - s * position[1]) + translate[0],
        scale * (s * position[0] + c * position[1]) + translate[1],
    )


def test_world_to_map_translation() -> None:
    assert world_to_map((1, 2), scale=1, rotation_rad=0, translate=(10, 20)) == (11, 22)


def test_world_to_map_scale() -> None:
    assert world_to_map((2, 3), scale=4, rotation_rad=0, translate=(0, 0)) == (8, 12)


def test_world_to_map_rotation() -> None:
    x, y = world_to_map((1, 0), scale=1, rotation_rad=math.pi / 2, translate=(0, 0))
    assert x == pytest.approx(0)
    assert y == pytest.approx(1)


def test_invalid_transform_rejected() -> None:
    with pytest.raises(ValueError):
        world_to_map((1, 2), scale=0, rotation_rad=0, translate=(0, 0))

