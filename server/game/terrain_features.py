"""
Procedural water (ponds + streams) and poor-soil marks for farmland parcels.
Used by world generation and one-time seeding for older databases.
"""
from __future__ import annotations

import random
from typing import Iterable

from server.game.constants import PLAYER_SPAWN, WORLD_H, WORLD_W


def _point_in_polygon(x: float, y: float, poly: list[dict]) -> bool:
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]["x"], poly[i]["y"]
        xj, yj = poly[j]["x"], poly[j]["y"]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_any_town(x: int, y: int, towns: list[dict]) -> bool:
    for t in towns:
        if _point_in_polygon(float(x), float(y), t["boundary"]):
            return True
    return False


def generate_water_features(
    rng: random.Random,
    node_positions: set[tuple[int, int]],
    towns: list[dict],
) -> set[tuple[int, int]]:
    """
    Ponds and winding streams. Avoids resource nodes, spawn safety, and town interiors.
    """
    sx, sy = PLAYER_SPAWN
    water: set[tuple[int, int]] = set()

    def ok_tile(tx: int, ty: int) -> bool:
        if not (8 <= tx < WORLD_W - 8 and 8 <= ty < WORLD_H - 8):
            return False
        if abs(tx - sx) <= 42 and abs(ty - sy) <= 42:
            return False
        if (tx, ty) in node_positions:
            return False
        if _point_in_any_town(tx, ty, towns):
            return False
        return True

    # Ponds
    for _ in range(55):
        cx = rng.randint(50, WORLD_W - 50)
        cy = rng.randint(50, WORLD_H - 50)
        if not ok_tile(cx, cy):
            continue
        rad = rng.randint(2, 5)
        for dx in range(-rad - 1, rad + 2):
            for dy in range(-rad - 1, rad + 2):
                if dx * dx + dy * dy <= rad * rad + rng.randint(0, 2):
                    tx, ty = cx + dx, cy + dy
                    if ok_tile(tx, ty):
                        water.add((tx, ty))

    # Streams (random walks)
    for _ in range(28):
        edge = rng.randint(0, 3)
        if edge == 0:
            x, y = rng.randint(30, WORLD_W - 30), 12
        elif edge == 1:
            x, y = rng.randint(30, WORLD_W - 30), WORLD_H - 13
        elif edge == 2:
            x, y = 12, rng.randint(30, WORLD_H - 30)
        else:
            x, y = WORLD_W - 13, rng.randint(30, WORLD_H - 30)

        length = rng.randint(55, 160)
        width = rng.choice([1, 1, 1, 2])
        for _s in range(length):
            if ok_tile(x, y):
                for wx in range(x, min(WORLD_W - 1, x + width)):
                    for wy in range(y, min(WORLD_H - 1, y + width)):
                        if ok_tile(wx, wy):
                            water.add((wx, wy))
            opts = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]
            dx, dy = rng.choice(opts)
            x = max(10, min(WORLD_W - 11, x + dx + rng.randint(-1, 1)))
            y = max(10, min(WORLD_H - 11, y + dy + rng.randint(-1, 1)))

    return water


def generate_poor_soil_for_parcels(
    rng: random.Random,
    parcels: Iterable[dict],
) -> set[tuple[int, int]]:
    """
    Some tiles in purchasable parcels need dirt improvement before tilling works.
    """
    poor: set[tuple[int, int]] = set()
    for p in parcels:
        w, h = int(p["w"]), int(p["h"])
        x0, y0 = int(p["x"]), int(p["y"])
        mode = rng.choice(("patchy", "patchy", "patchy", "good", "full_bad"))
        if mode == "good":
            continue
        if mode == "full_bad":
            for dx in range(w):
                for dy in range(h):
                    poor.add((x0 + dx, y0 + dy))
            continue
        for dx in range(w):
            for dy in range(h):
                if rng.random() < 0.22:
                    poor.add((x0 + dx, y0 + dy))
    return poor
