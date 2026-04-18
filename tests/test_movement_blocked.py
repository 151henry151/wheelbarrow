"""Movement: blocked tiles block entry, not standing on or leaving."""
from __future__ import annotations

import math

import pytest

from server.game.movement import integrate_player_movement


def test_can_leave_blocked_tile_structure_or_pile() -> None:
    """Standing on a blocked tile (e.g. NPC market), movement must reach adjacent grass."""
    water: set[tuple[int, int]] = set()
    bridges: set[tuple[int, int]] = set()
    roads: set[tuple[int, int]] = set()
    blocked = {(510, 510)}

    player = {
        "x": 510.5,
        "y": 510.5,
        "angle": 0.0,
        "_input_fwd": 1.0,
        "_input_turn": 0.0,
        "bucket": {},
        "wb_bucket_level": 1,
        "wb_barrow_level": 1,
        "wb_handle_level": 1,
        "flat_tire": 0,
    }
    x0, y0 = player["x"], player["y"]
    ev = integrate_player_movement(player, 0.05, water, bridges, blocked, roads)
    assert ev == []
    assert player["x"] > x0 + 1e-6
    assert abs(player["y"] - y0) < 0.5


def test_cannot_enter_blocked_tile_from_outside() -> None:
    blocked = {(100, 100)}
    # Stand west of the blocked tile; driving east would enter (100, 100).
    player = {
        "x": 99.5,
        "y": 100.5,
        "angle": 0.0,
        "_input_fwd": 1.0,
        "_input_turn": 0.0,
        "bucket": {},
        "wb_bucket_level": 1,
        "wb_barrow_level": 1,
        "wb_handle_level": 1,
        "flat_tire": 0,
    }
    x0, y0 = player["x"], player["y"]
    integrate_player_movement(player, 0.2, set(), set(), blocked, set())
    assert math.isclose(player["x"], x0) and math.isclose(player["y"], y0)
