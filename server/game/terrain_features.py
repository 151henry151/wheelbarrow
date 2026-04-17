"""
Procedural water (ponds + streams) and poor-soil marks for farmland parcels.
Used by world generation and one-time seeding for older databases.
"""
from __future__ import annotations

import math
import random
from typing import Iterable

from server.game.constants import PLAYER_SPAWN, WORLD_H, WORLD_W

# Keep ponds/streams out of town *cores* and NPC clusters — not the full Voronoi polygon.
# (Town boundaries partition the whole map; excluding “inside polygon” blocked all water.)
WATER_EXCLUSION_RADIUS_FROM_TOWN_CENTER = 92
# Chebyshev padding around each NPC shop tile from npc_district
WATER_EXCLUSION_PADDING_AROUND_NPC = 10
# No wild water inside this Chebyshev distance of PLAYER_SPAWN (smaller = water appears sooner when exploring).
SPAWN_WATER_EXCLUSION = 30
# Town whose center is PLAYER_SPAWN would otherwise exclude a huge disk (92 tiles) and block all nearby rivers/ponds.
SPAWN_TOWN_WATER_CORE_RADIUS = 22


def _too_close_to_town_core_or_shops(x: int, y: int, towns: list[dict]) -> bool:
    """True if water should not appear here (near a town center or NPC site)."""
    sx, sy = PLAYER_SPAWN
    for t in towns:
        cx, cy = int(t["center_x"]), int(t["center_y"])
        dist = math.hypot(x - cx, y - cy)
        if cx == sx and cy == sy:
            if dist < SPAWN_TOWN_WATER_CORE_RADIUS:
                return True
        elif dist < WATER_EXCLUSION_RADIUS_FROM_TOWN_CENTER:
            return True
        d = t.get("npc_district")
        if not d or not isinstance(d, dict):
            continue
        for pos in d.values():
            if not pos or len(pos) < 2:
                continue
            px, py = int(pos[0]), int(pos[1])
            if max(abs(x - px), abs(y - py)) <= WATER_EXCLUSION_PADDING_AROUND_NPC:
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
        if abs(tx - sx) <= SPAWN_WATER_EXCLUSION and abs(ty - sy) <= SPAWN_WATER_EXCLUSION:
            return False
        if (tx, ty) in node_positions:
            return False
        if _too_close_to_town_core_or_shops(tx, ty, towns):
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


def extra_ponds_outside_spawn_ring(
    rng: random.Random,
    existing: set[tuple[int, int]],
    node_positions: set[tuple[int, int]],
    towns: list[dict],
) -> set[tuple[int, int]]:
    """
    Extra small ponds in an annulus just outside the spawn dry zone.
    For one-time migration on older worlds that had a larger exclusion — adds visible water
    without replacing existing water/bridges.
    """
    sx, sy = PLAYER_SPAWN
    added: set[tuple[int, int]] = set()

    def ok_tile(tx: int, ty: int) -> bool:
        if not (8 <= tx < WORLD_W - 8 and 8 <= ty < WORLD_H - 8):
            return False
        if abs(tx - sx) <= SPAWN_WATER_EXCLUSION and abs(ty - sy) <= SPAWN_WATER_EXCLUSION:
            return False
        if (tx, ty) in node_positions:
            return False
        if (tx, ty) in existing or (tx, ty) in added:
            return False
        if _too_close_to_town_core_or_shops(tx, ty, towns):
            return False
        return True

    for _ in range(36):
        ang = rng.random() * 2 * math.pi
        dist = rng.uniform(SPAWN_WATER_EXCLUSION + 6, SPAWN_WATER_EXCLUSION + 55)
        cx = int(sx + math.cos(ang) * dist)
        cy = int(sy + math.sin(ang) * dist)
        rad = rng.randint(2, 4)
        for dx in range(-rad - 1, rad + 2):
            for dy in range(-rad - 1, rad + 2):
                if dx * dx + dy * dy <= rad * rad + rng.randint(0, 2):
                    tx, ty = cx + dx, cy + dy
                    if ok_tile(tx, ty):
                        added.add((tx, ty))
    return added


def generate_poor_soil_for_parcels(
    rng: random.Random,
    parcels: Iterable[dict],
) -> set[tuple[int, int]]:
    """
    Patchy poor soil inside purchasable parcels: Gaussian blobs + per-parcel strength.
    Some parcels skew mostly good or mostly bad by chance; none are forced all-bad or all-good.
    """
    poor: set[tuple[int, int]] = set()
    for p in parcels:
        w, h = int(p["w"]), int(p["h"])
        x0, y0 = int(p["x"]), int(p["y"])
        area = w * h
        if area <= 0:
            continue

        n_blobs = rng.randint(1, max(1, min(6, max(2, area // 35))))
        centers = [
            (rng.uniform(0, max(0.1, w - 1)), rng.uniform(0, max(0.1, h - 1)))
            for _ in range(n_blobs)
        ]
        sigmas = [
            max(1.2, min(w, h) * rng.uniform(0.14, 0.38))
            for _ in range(n_blobs)
        ]
        parcel_strength = rng.uniform(0.1, 0.48)

        scores: list[tuple[int, int, float]] = []
        for dx in range(w):
            for dy in range(h):
                s = 0.0
                for (cx, cy), sig in zip(centers, sigmas):
                    d2 = (dx - cx) ** 2 + (dy - cy) ** 2
                    s += math.exp(-d2 / (2.0 * sig * sig))
                scores.append((dx, dy, s))
        max_s = max((t[2] for t in scores), default=1.0)
        if max_s <= 0:
            max_s = 1.0
        for dx, dy, s in scores:
            norm = s / max_s
            p_tile = min(0.48, parcel_strength * (0.1 + 0.9 * norm))
            if rng.random() < p_tile:
                poor.add((x0 + dx, y0 + dy))
    return poor
