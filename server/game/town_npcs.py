"""
Per-town NPC business district: market + three shops clustered inside the town polygon.
"""
from __future__ import annotations

import json
import random
from typing import Any

DISTRICT_KEYS = ("market", "seed_shop", "general_store", "repair_shop")

# Base lattice: four sites around one anchor, not touching (Chebyshev >= 2 between pairs).
# Applied offsets are multiplied by PATTERN_SCALE so shops sit ~3× further apart than the first revision.
PATTERN_SCALE = 3

# Relative offsets (before scale); max extent ~6 → ~18 tiles after scale
_SPREAD_PATTERNS: list[list[tuple[int, int]]] = [
    [(0, 0), (4, 0), (0, 5), (4, 5)],
    [(1, 1), (5, 1), (1, 6), (5, 6)],
    [(0, 2), (5, 0), (2, 6), (5, 4)],
    [(0, 0), (5, 2), (1, 5), (5, 5)],
    [(2, 0), (6, 1), (0, 5), (6, 5)],
    [(0, 1), (4, 0), (1, 6), (5, 4)],
    [(1, 0), (5, 2), (0, 5), (4, 6)],
]


def _scale_offsets(pattern: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return [(dx * PATTERN_SCALE, dy * PATTERN_SCALE) for dx, dy in pattern]


def _pattern_spread_ok(tiles: list[tuple[int, int]]) -> bool:
    if len(set(tiles)) < 4:
        return False
    for i, a in enumerate(tiles):
        for b in tiles[i + 1 :]:
            if max(abs(a[0] - b[0]), abs(a[1] - b[1])) < 2:
                return False
    return True


def _pattern_wide_enough(tiles: list[tuple[int, int]]) -> bool:
    """Loose clustering: every pair at least Chebyshev 6 apart (~3× legacy 'not touching' spacing)."""
    for i, a in enumerate(tiles):
        for b in tiles[i + 1 :]:
            if max(abs(a[0] - b[0]), abs(a[1] - b[1])) < 6:
                return False
    return True


def district_spread_ok(d: dict[str, list[int]]) -> bool:
    """True if four sites exist, none touching, and spacing matches current wide layout rules."""
    tiles: list[tuple[int, int]] = []
    for k in DISTRICT_KEYS:
        v = d.get(k)
        if not v or len(v) < 2:
            return False
        tiles.append((int(v[0]), int(v[1])))
    if not _pattern_spread_ok(tiles):
        return False
    return _pattern_wide_enough(tiles)


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


def _tile_inside_town(tx: int, ty: int, poly: list[dict]) -> bool:
    return _point_in_polygon(tx + 0.5, ty + 0.5, poly)


def place_npc_district(town: dict, rng: random.Random) -> dict[str, list[int]]:
    """
    Pick four distinct walkable tiles inside the town boundary, all near one anchor.
    Returns { "market": [x,y], "seed_shop": [...], ... }.
    """
    poly: list[dict] = town.get("boundary") or []
    cx, cy = int(town["center_x"]), int(town["center_y"])
    if len(poly) < 3:
        off = _scale_offsets(_SPREAD_PATTERNS[0])
        return {DISTRICT_KEYS[i]: [cx + off[i][0], cy + off[i][1]] for i in range(4)}

    radius = max(30, int(town.get("radius", 80)))

    # Candidate anchor tiles: biased toward center, jittered
    candidates: list[tuple[int, int]] = []
    for _ in range(80):
        ax = cx + rng.randint(-radius // 3, radius // 3)
        ay = cy + rng.randint(-radius // 3, radius // 3)
        candidates.append((ax, ay))
    # Include exact center attempts
    for d in range(0, 12):
        candidates.append((cx + d, cy))
        candidates.append((cx - d, cy))
        candidates.append((cx, cy + d))
        candidates.append((cx, cy - d))

    rng.shuffle(_SPREAD_PATTERNS)

    for ax, ay in candidates:
        if not _tile_inside_town(ax, ay, poly):
            continue
        for pattern in _SPREAD_PATTERNS:
            offs = _scale_offsets(pattern)
            tiles: list[tuple[int, int]] = []
            ok = True
            for dx, dy in offs:
                tx, ty = ax + dx, ay + dy
                if not _tile_inside_town(tx, ty, poly):
                    ok = False
                    break
                tiles.append((tx, ty))
            if not ok or not _pattern_spread_ok(tiles) or not _pattern_wide_enough(tiles):
                continue
            return {k: [tiles[i][0], tiles[i][1]] for i, k in enumerate(DISTRICT_KEYS)}

    # Last resort: wider anchor search — footprint ~18×18 tiles after scale
    span = min(max(radius, 80), 180)
    for ax in range(cx - span, cx + span + 1):
        for ay in range(cy - span, cy + span + 1):
            if not _tile_inside_town(ax, ay, poly):
                continue
            for pattern in _SPREAD_PATTERNS:
                offs = _scale_offsets(pattern)
                tiles = []
                ok = True
                for dx, dy in offs:
                    tx, ty = ax + dx, ay + dy
                    if not _tile_inside_town(tx, ty, poly):
                        ok = False
                        break
                    tiles.append((tx, ty))
                if ok and _pattern_spread_ok(tiles) and _pattern_wide_enough(tiles):
                    return {k: [tiles[i][0], tiles[i][1]] for i, k in enumerate(DISTRICT_KEYS)}

    # Final fallback: offset anchor from town center (scaled pattern ~18 tiles across)
    for ox in range(-24, 25):
        for oy in range(-24, 25):
            base_x, base_y = cx + ox, cy + oy
            for pattern in _SPREAD_PATTERNS:
                offs = _scale_offsets(pattern)
                tiles = []
                ok = True
                for dx, dy in offs:
                    tx, ty = base_x + dx, base_y + dy
                    if not _tile_inside_town(tx, ty, poly):
                        ok = False
                        break
                    tiles.append((tx, ty))
                if ok and _pattern_spread_ok(tiles) and _pattern_wide_enough(tiles):
                    return {k: [tiles[i][0], tiles[i][1]] for i, k in enumerate(DISTRICT_KEYS)}

    off = _scale_offsets(_SPREAD_PATTERNS[0])
    return {DISTRICT_KEYS[i]: [cx + off[i][0], cy + off[i][1]] for i in range(4)}


def parse_npc_district(raw: Any) -> dict[str, list[int]] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict):
        return None
    out: dict[str, list[int]] = {}
    for k in DISTRICT_KEYS:
        v = raw.get(k)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            out[k] = [int(v[0]), int(v[1])]
    return out if len(out) == 4 else None
