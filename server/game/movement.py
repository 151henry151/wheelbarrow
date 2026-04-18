"""
Continuous tile-space movement: float x, y and heading angle (radians).
Angle 0 = east (+x), π/2 = south (+y); velocity (cos θ, sin θ).
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger("uvicorn.error")

from server.game.constants import (
    RESOURCE_WEIGHTS,
    RESOURCE_WEIGHT_DEFAULT,
    WORLD_W,
    WORLD_H,
    WB_BARROW_CHASSIS_WEIGHT,
    WB_HANDLE_CHASSIS_WEIGHT,
)
from server.game.terrain_elevation import elevation_raw
from server.game.wb_condition import apply_move_decay, effective_bucket_cap

_MAX_W_UNIT = 2.5  # match client RESOURCE_WEIGHT_MAX_UNIT

BASE_MOVE_TILES_PER_SEC = 6.0
TURN_RADIANS_PER_SEC = 2.8
# Faster on dirt roads; gentle steering aligns to road axis when on a road tile.
ROAD_SPEED_MULT = 1.38
ROAD_SNAP_STRENGTH = 2.6  # radians/sec toward cardinal road axis when on road


def player_tile_xy(p: dict) -> tuple[int, int]:
    return (int(math.floor(float(p["x"]))), int(math.floor(float(p["y"]))))


def load_speed_mult(player: dict) -> float:
    """>=1.0 — heavier load slows movement (same curve as client)."""
    bucket = player.get("bucket") or {}
    cap = float(effective_bucket_cap(player))
    total_weight = 0.0
    for rtype, amount in bucket.items():
        w = RESOURCE_WEIGHTS.get(rtype, RESOURCE_WEIGHT_DEFAULT)
        total_weight += w * float(amount)
    bl = player.get("wb_barrow_level", 1)
    hl = player.get("wb_handle_level", 1)
    total_weight += WB_BARROW_CHASSIS_WEIGHT.get(bl, 0.0)
    total_weight += WB_HANDLE_CHASSIS_WEIGHT.get(hl, 0.0)
    max_weight = cap * _MAX_W_UNIT
    if max_weight <= 0:
        return 1.0
    return max(0.5, 1.0 + (total_weight / max_weight) * 2.0)


def terrain_interval_mult(px: float, py: float, angle: float) -> float:
    """Match client Terrain.moveIntervalMult: uphill → larger → slower."""
    tx = int(math.floor(px))
    ty = int(math.floor(py))
    fx = math.cos(angle)
    fy = math.sin(angle)
    nx = int(math.floor(px + fx * 0.45))
    ny = int(math.floor(py + fy * 0.45))
    nx = max(0, min(WORLD_W - 1, nx))
    ny = max(0, min(WORLD_H - 1, ny))
    dh = elevation_raw(nx, ny) - elevation_raw(tx, ty)
    m = 1.0 + 2.4 * dh
    return max(0.76, min(1.24, m))


def angle_to_cardinal_dir(angle: float) -> str:
    """Nearest up/down/left/right for legacy actions (water, bridge)."""
    a = angle
    two_pi = 2.0 * math.pi
    a = ((a + math.pi) % two_pi) - math.pi
    best = "down"
    best_dot = -99.0
    for name, (vx, vy) in (
        ("right", (1.0, 0.0)),
        ("left", (-1.0, 0.0)),
        ("down", (0.0, 1.0)),
        ("up", (0.0, -1.0)),
    ):
        d = math.cos(a) * vx + math.sin(a) * vy
        if d > best_dot:
            best_dot = d
            best = name
    return best


def _walkable_tile(
    tx: int,
    ty: int,
    water_tiles: set[tuple[int, int]],
    bridge_tiles: set[tuple[int, int]],
) -> bool:
    if (tx, ty) in bridge_tiles:
        return True
    return (tx, ty) not in water_tiles


def _segment_hits_water(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    water_tiles: set[tuple[int, int]],
    bridge_tiles: set[tuple[int, int]],
) -> bool:
    for t in (0.12, 0.35, 0.55, 0.75, 0.92):
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        tx, ty = int(math.floor(x)), int(math.floor(y))
        if not _walkable_tile(tx, ty, water_tiles, bridge_tiles):
            return True
    return False


def _segment_hits_blocked(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    blocked: set[tuple[int, int]],
) -> bool:
    """Block entering a blocked tile from outside. Samples still on the departure tile are ignored so
    players can drive off structures / nodes / pile tiles they are already standing on."""
    sx, sy = int(math.floor(x0)), int(math.floor(y0))
    for t in (0.12, 0.35, 0.55, 0.75, 0.92):
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        tx, ty = int(math.floor(x)), int(math.floor(y))
        if (tx, ty) == (sx, sy):
            continue
        if (tx, ty) in blocked:
            return True
    return False


def _road_snap_angle(
    tx: int,
    ty: int,
    angle: float,
    road_tiles: set[tuple[int, int]],
    dt: float,
) -> float:
    if (tx, ty) not in road_tiles:
        return angle
    has_e = (tx + 1, ty) in road_tiles
    has_w = (tx - 1, ty) in road_tiles
    has_n = (tx, ty - 1) in road_tiles
    has_s = (tx, ty + 1) in road_tiles
    ew = has_e or has_w
    ns = has_n or has_s
    if not ew and not ns:
        return angle
    if ew and not ns:
        target = 0.0 if math.cos(angle) >= 0 else math.pi
    elif ns and not ew:
        target = math.pi / 2 if math.sin(angle) >= 0 else -math.pi / 2
    else:
        cands = (0.0, math.pi, math.pi / 2, -math.pi / 2)
        target = min(
            cands,
            key=lambda c: abs(((angle - c + math.pi) % (2 * math.pi)) - math.pi),
        )
    da = ((target - angle + math.pi) % (2 * math.pi)) - math.pi
    return angle + da * min(1.0, ROAD_SNAP_STRENGTH * dt)


def integrate_player_movement(
    player: dict,
    dt: float,
    water_tiles: set[tuple[int, int]],
    bridge_tiles: set[tuple[int, int]],
    blocked_tiles: set[tuple[int, int]],
    road_tiles: set[tuple[int, int]],
) -> list[str]:
    """Apply _input_fwd / _input_turn; returns wheelbarrow events from wear."""
    fwd = float(player.get("_input_fwd", 0.0) or 0.0)
    turn = float(player.get("_input_turn", 0.0) or 0.0)
    fwd = max(-1.0, min(1.0, fwd))
    turn = max(-1.0, min(1.0, turn))

    angle = float(player.get("angle", math.pi / 2))

    if abs(turn) > 1e-6:
        angle += turn * TURN_RADIANS_PER_SEC * dt
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi

    tx0, ty0 = player_tile_xy(player)
    if (tx0, ty0) in road_tiles and (abs(fwd) > 1e-6 or abs(turn) < 1e-6):
        angle = _road_snap_angle(tx0, ty0, angle, road_tiles, dt)

    player["angle"] = angle

    events: list[str] = []

    if abs(fwd) < 1e-6:
        return events

    load_m = load_speed_mult(player)
    flat_m = 3.0 if player.get("flat_tire") else 1.0
    terr_m = terrain_interval_mult(float(player["x"]), float(player["y"]), angle)
    on_road = (tx0, ty0) in road_tiles
    road_m = ROAD_SPEED_MULT if on_road else 1.0
    speed = BASE_MOVE_TILES_PER_SEC / load_m / flat_m / terr_m * road_m
    dist = abs(fwd) * speed * dt
    if dist <= 1e-9:
        return events

    sign = 1.0 if fwd > 0 else -1.0
    dx = math.cos(angle) * dist * sign
    dy = math.sin(angle) * dist * sign

    ox, oy = float(player["x"]), float(player["y"])
    nx = ox + dx
    ny = oy + dy

    nx = max(0.0, min(float(WORLD_W) - 1e-7, nx))
    ny = max(0.0, min(float(WORLD_H) - 1e-7, ny))

    pid = player.get("id", "?")
    if _segment_hits_water(ox, oy, nx, ny, water_tiles, bridge_tiles):
        logger.warning("DBG move blocked WATER pid=%s pos=(%.2f,%.2f) angle=%.3f fwd=%.2f", pid, ox, oy, angle, fwd)
        return events
    if _segment_hits_blocked(ox, oy, nx, ny, blocked_tiles):
        logger.warning("DBG move blocked SEGMENT pid=%s pos=(%.2f,%.2f) angle=%.3f fwd=%.2f", pid, ox, oy, angle, fwd)
        return events

    tx, ty = int(math.floor(nx)), int(math.floor(ny))
    sx, sy = int(math.floor(ox)), int(math.floor(oy))
    if not _walkable_tile(tx, ty, water_tiles, bridge_tiles):
        logger.warning("DBG move blocked DEST_WATER pid=%s pos=(%.2f,%.2f) dest=(%d,%d)", pid, ox, oy, tx, ty)
        return events
    # Reject entering a blocked tile from another tile; allow leaving or nudging within same tile.
    if (tx, ty) in blocked_tiles and (tx, ty) != (sx, sy):
        logger.warning("DBG move blocked DEST_BLOCKED pid=%s pos=(%.2f,%.2f) dest=(%d,%d)", pid, ox, oy, tx, ty)
        return events
    logger.info("DBG move OK pid=%s (%.2f,%.2f)->(%.2f,%.2f) fwd=%.2f", pid, ox, oy, nx, ny, fwd)

    player["x"], player["y"] = nx, ny

    player["_wear_accum"] = float(player.get("_wear_accum", 0.0)) + dist
    while player["_wear_accum"] >= 1.0:
        player["_wear_accum"] -= 1.0
        events.extend(apply_move_decay(player))

    return events
