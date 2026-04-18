"""Server elevation field (must match client/js/terrain.js)."""
from __future__ import annotations

import math

from server.game.terrain_elevation import (
    WORLD_Y_SCALE,
    elevation_raw,
    elevation_raw_float,
    world_y_units,
)


def _ref_raw(tx: int, ty: int) -> float:
    fx = tx * 0.06
    fy = ty * 0.07
    low = (
        math.sin(fx + fy * 0.71) * 0.5
        + math.cos(fx * 0.55 - fy * 0.8) * 0.35
        + math.sin((tx + ty) * 0.095) * 0.15
    )
    med = math.sin(tx * 0.14 + ty * 0.11) * 0.12 + math.cos(tx * 0.09 - ty * 0.13) * 0.08
    return max(-1.0, min(1.0, low + med))


def test_elevation_raw_clamped() -> None:
    for tx in (0, 17, 100, 500, 999):
        for ty in (0, 33, 200, 500, 999):
            r = elevation_raw(tx, ty)
            assert -1.0 <= r <= 1.0


def test_world_y_formula() -> None:
    tx, ty = 333, 444
    assert world_y_units(tx, ty) == 2.0 + elevation_raw(tx, ty) * WORLD_Y_SCALE


def test_matches_reference_implementation() -> None:
    for tx, ty in ((100, 200), (500, 500), (812, 91)):
        assert elevation_raw(tx, ty) == _ref_raw(tx, ty)


def test_elevation_raw_float_matches_integers() -> None:
    for tx, ty in ((3, 4), (100, 200)):
        assert elevation_raw_float(float(tx), float(ty)) == elevation_raw(tx, ty)


def test_elevation_raw_float_smooth() -> None:
    a = elevation_raw_float(10.0, 20.0)
    b = elevation_raw_float(10.25, 20.0)
    assert a != b
