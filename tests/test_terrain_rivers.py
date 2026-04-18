"""Geometry helpers for major rivers."""
from __future__ import annotations

import random

import pytest

from server.game.terrain_features import (
    MAJOR_RIVER_CHAIN_MIN,
    _densify_polyline,
    _dist_point_to_segment,
    generate_major_rivers,
)


def test_dist_point_to_segment_endpoints() -> None:
    assert _dist_point_to_segment(0.0, 0.0, 0.0, 0.0, 10.0, 0.0) == pytest.approx(0.0)
    assert _dist_point_to_segment(10.0, 0.0, 0.0, 0.0, 10.0, 0.0) == pytest.approx(0.0)


def test_dist_point_to_segment_perpendicular_midpoint() -> None:
    d = _dist_point_to_segment(5.0, 3.0, 0.0, 0.0, 10.0, 0.0)
    assert d == pytest.approx(3.0)


def test_densify_adds_points() -> None:
    pts = [(0.0, 0.0), (10.0, 0.0)]
    dense = _densify_polyline(pts, step=2.0)
    assert len(dense) >= 3
    assert dense[0] == (0.0, 0.0)
    assert dense[-1] == (10.0, 0.0)


def test_generate_major_rivers_shape() -> None:
    rng = random.Random(12345)
    towns = [
        {"center_x": 100 + i * 45, "center_y": 200 + (i % 3) * 5, "npc_district": None}
        for i in range(MAJOR_RIVER_CHAIN_MIN + 4)
    ]
    nodes: set[tuple[int, int]] = set()
    tiles = generate_major_rivers(rng, nodes, towns)
    assert len(tiles) > 500
    # Roughly within world strip
    for x, y in list(tiles)[:50]:
        assert 8 <= x < 1000 - 8
        assert 8 <= y < 1000 - 8


def test_generate_major_rivers_respects_blocked() -> None:
    rng = random.Random(777)
    towns = [
        {"center_x": 300 + i * 40, "center_y": 400, "npc_district": None}
        for i in range(12)
    ]
    nodes = {(320, 400)}
    blocked = {(320, 400)}
    tiles = generate_major_rivers(rng, nodes, towns, extra_blocked=blocked)
    assert (320, 400) not in tiles
