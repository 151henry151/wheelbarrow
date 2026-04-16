"""
Procedural world generation.

Runs once at startup (guarded by world_gen_state.done). Generates:
  - 40 towns with organic, irregular polygon boundaries
  - ~500 resource nodes distributed by biome
  - ~700 land parcels of varying size and price
"""
import math
import random
import json
from server.game.constants import (
    WORLD_W, WORLD_H,
    TOWN_ADJ, TOWN_NOUN, TOWN_COUNT, TOWN_MIN_DIST,
    TOWN_RADIUS_MIN, TOWN_RADIUS_MAX,
    PARCEL_W_RANGE, PARCEL_H_RANGE,
    PARCEL_PRICE_PER_TILE, PARCEL_RESOURCE_BONUS, PARCEL_MIN_PRICE,
    TOWN_PARCELS_PER_TOWN, WILDERNESS_PARCELS,
    PLAYER_SPAWN,
)
from server.game.town_npcs import place_npc_district
from server.db import queries

# ---- Biome helpers ----------------------------------------------------------

def _biome(x: int, y: int) -> str:
    """
    Simple smooth biome from position. Returns one of:
    'forest', 'rocky', 'plains', 'wetland'
    """
    nx, ny = x / 250, y / 250
    v = (math.sin(nx * 2.1) * math.cos(ny * 1.7) +
         math.cos(nx * 1.3 + ny * 0.9) + 2.0) / 4.0
    if v < 0.25: return "wetland"
    if v < 0.50: return "plains"
    if v < 0.75: return "forest"
    return "rocky"


BIOME_RESOURCES = {
    "forest":  [("wood",    80,  0.04), ("dirt",   50, 0.06)],
    "rocky":   [("stone",  120,  0.02), ("gravel", 100, 0.03)],
    "plains":  [("dirt",    60,  0.07), ("topsoil", 80, 0.40)],
    # Manure is a byproduct of player-built Stables — not a wild resource.
    # Compost is a byproduct of player-built Compost Heaps — not a wild resource.
    "wetland": [("clay",   100,  0.05), ("topsoil", 60, 0.15)],
}

# ---- Town placement ---------------------------------------------------------

def _place_towns(rng: random.Random) -> list[dict]:
    """
    Place TOWN_COUNT towns with Voronoi-clipped polygon boundaries.
    Two-pass approach: collect all centers first, then generate each polygon
    with knowledge of every other center so vertices never cross a neighbor's
    perpendicular bisector — guaranteeing no two town polygons ever overlap.
    """
    # Pass 1: place all centers
    centres: list[tuple[int,int]] = []
    spawn_cx, spawn_cy = PLAYER_SPAWN
    centres.append((spawn_cx, spawn_cy))

    attempts = 0
    while len(centres) < TOWN_COUNT and attempts < 2000:
        attempts += 1
        cx = rng.randint(80, WORLD_W - 80)
        cy = rng.randint(80, WORLD_H - 80)
        if any(math.hypot(cx - ox, cy - oy) < TOWN_MIN_DIST for ox, oy in centres):
            continue
        centres.append((cx, cy))

    # Pass 2: generate a Voronoi-clipped polygon for each center
    towns: list[dict] = []
    names_used: set = set()
    for i, (cx, cy) in enumerate(centres):
        other = [(ox, oy) for j, (ox, oy) in enumerate(centres) if j != i]

        adj  = rng.choice(TOWN_ADJ)
        noun = rng.choice(TOWN_NOUN)
        name = f"{adj}{noun}"
        while name in names_used:
            adj  = rng.choice(TOWN_ADJ)
            noun = rng.choice(TOWN_NOUN)
            name = f"{adj}{noun}"
        names_used.add(name)

        radius = 120 if i == 0 else rng.randint(TOWN_RADIUS_MIN, TOWN_RADIUS_MAX)
        points = 16  if i == 0 else rng.randint(10, 18)
        poly   = _generate_polygon(cx, cy, radius, rng, points=points, voronoi_centres=other)
        towns.append({
            "name": name, "center_x": cx, "center_y": cy,
            "radius": radius, "boundary": poly,
        })

    return towns


def _generate_polygon(cx: int, cy: int, radius: int, rng: random.Random,
                      points: int = 12, voronoi_centres=None) -> list[dict]:
    """
    Generate an irregular polygon around (cx, cy) with approximate radius.

    If voronoi_centres is a list of (ox, oy) tuples, each vertex is clipped to
    the Voronoi cell: no vertex will extend past the perpendicular bisector to
    any neighboring center, ensuring polygons never overlap.

    Returns list of {x, y} dicts for JSON storage.
    """
    verts = []
    for i in range(points):
        angle  = (2 * math.pi * i / points) + rng.uniform(-0.2, 0.2)
        r      = radius * rng.uniform(0.6, 1.4)
        r      = max(20, min(r, radius * 1.5))

        if voronoi_centres:
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            for (ox, oy) in voronoi_centres:
                dvx, dvy = ox - cx, oy - cy
                # Projection of the direction vector onto the vector toward
                # the other center. Positive means the vertex is heading toward
                # that center; negative means away (no constraint needed).
                proj = cos_a * dvx + sin_a * dvy
                if proj <= 0:
                    continue
                # Distance to the perpendicular bisector along this direction:
                #   r_bisect = |D|² / (2 · proj)
                # Keep a small margin (0.9) so boundaries don't touch exactly.
                r_bisect = (dvx * dvx + dvy * dvy) / (2.0 * proj) * 0.90
                if r_bisect < r:
                    r = r_bisect
            r = max(15, r)   # don't collapse to a point

        vx = int(cx + math.cos(angle) * r)
        vy = int(cy + math.sin(angle) * r)
        vx = max(5, min(WORLD_W - 5, vx))
        vy = max(5, min(WORLD_H - 5, vy))
        verts.append({"x": vx, "y": vy})
    return verts


def _point_in_polygon(x: float, y: float, poly: list[dict]) -> bool:
    """Ray-cast point-in-polygon test."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]["x"], poly[i]["y"]
        xj, yj = poly[j]["x"], poly[j]["y"]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _find_town_for_point(x: int, y: int, towns: list[dict]) -> int | None:
    """Return 0-based index of the town that contains (x,y), or None."""
    for i, t in enumerate(towns):
        if _point_in_polygon(x, y, t["boundary"]):
            return i
    return None

# ---- Resource node generation -----------------------------------------------

def _generate_nodes(rng: random.Random) -> list[dict]:
    """
    Scatter ~500 resource nodes across the world by biome.
    Near spawn (±30 tiles) is always seeded with starter resources.
    """
    nodes: list[dict] = []
    sx, sy = PLAYER_SPAWN

    # Guaranteed starter resources — placed near the NPC shops (50-70 tiles from spawn)
    # so new players have to travel a bit to find them.
    # Only truly wild resources here: wood, stone, gravel, clay, topsoil, dirt.
    # Manure (from Stable) and compost (from Compost Heap) are never wild.
    for x, y, rtype, max_a, rate in [
        (sx-55, sy-8,  "wood",    80, 0.04),
        (sx-52, sy+5,  "stone",  120, 0.02),
        (sx+52, sy-8,  "wood",    80, 0.04),
        (sx+55, sy+5,  "gravel", 100, 0.03),
        (sx-50, sy+10, "gravel", 100, 0.03),
        (sx+50, sy+10, "clay",   100, 0.05),
        (sx-5,  sy-58, "topsoil", 80, 0.40),
        (sx+8,  sy-55, "stone",  120, 0.02),
        (sx-5,  sy+55, "clay",   100, 0.05),
        (sx+8,  sy+58, "dirt",    60, 0.07),
    ]:
        nodes.append({
            "x": x, "y": y, "node_type": rtype,
            "current_amount": round(max_a * 0.8, 1),
            "max_amount": max_a, "replenish_rate": rate,
        })

    # Protected zone: keep the spawn tile clear so players start on an empty field
    def near_spawn(x, y):
        return abs(x - sx) <= 35 and abs(y - sy) <= 35

    # Grid scatter: every ~25 tiles, 35% chance of a node
    for gx in range(0, WORLD_W, 25):
        for gy in range(0, WORLD_H, 25):
            if rng.random() > 0.35:
                continue
            x = gx + rng.randint(0, 24)
            y = gy + rng.randint(0, 24)
            x = max(5, min(WORLD_W - 5, x))
            y = max(5, min(WORLD_H - 5, y))
            if near_spawn(x, y):
                continue

            biome   = _biome(x, y)
            options = BIOME_RESOURCES[biome]
            rtype, max_a, rate = rng.choice(options)

            # Farther from spawn → lower current amount (depleted over time)
            dist      = math.hypot(x - sx, y - sy)
            freshness = max(0.3, 1.0 - dist / (WORLD_W * 0.6))

            nodes.append({
                "x": x, "y": y, "node_type": rtype,
                "current_amount": round(max_a * 0.5 * freshness, 1),
                "max_amount": max_a, "replenish_rate": rate,
            })

    return nodes

# ---- Parcel generation ------------------------------------------------------

def _generate_parcels(rng: random.Random, towns: list[dict],
                      node_list: list[dict]) -> list[dict]:
    """
    Generate variable-size rectangular parcels within towns and in the wilderness.
    Returns list of parcel dicts with town_idx (index into towns list, or None).
    """
    parcels: list[dict] = []
    # Quick lookup: node positions → node data
    node_map = {(n["x"], n["y"]): n for n in node_list}

    # occupied[tx][ty] = True if tile is inside an existing parcel
    occupied: set[tuple] = set()

    # Protected tiles: don't place parcels over NPC districts / spawn
    protected: set[tuple] = set()
    for dx0 in range(-3, 4):
        for dy0 in range(-3, 4):
            protected.add((PLAYER_SPAWN[0] + dx0, PLAYER_SPAWN[1] + dy0))
    for town in towns:
        district = town.get("npc_district") or {}
        for pos in district.values():
            if not pos or len(pos) < 2:
                continue
            px, py = int(pos[0]), int(pos[1])
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    protected.add((px + dx, py + dy))

    def _count_resources(x, y, w, h):
        return sum(
            1 for (nx, ny) in node_map
            if x <= nx < x + w and y <= ny < y + h
        )

    def _try_place(x, y, w, h, town_idx):
        if x < 5 or y < 5 or x + w > WORLD_W - 5 or y + h > WORLD_H - 5:
            return None
        tiles = frozenset((x + dx, y + dy) for dx in range(w) for dy in range(h))
        if tiles & occupied:
            return None
        if tiles & protected:
            return None
        occupied.update(tiles)
        rc    = _count_resources(x, y, w, h)
        price = max(PARCEL_MIN_PRICE, w * h * PARCEL_PRICE_PER_TILE + rc * PARCEL_RESOURCE_BONUS)
        return {
            "x": x, "y": y, "w": w, "h": h,
            "price": price, "town_idx": town_idx,
        }

    # Town parcels
    for t_idx, town in enumerate(towns):
        cx, cy, radius = town["center_x"], town["center_y"], town["radius"]
        count  = rng.randint(*TOWN_PARCELS_PER_TOWN)
        placed = 0
        for _ in range(count * 8):   # max attempts
            if placed >= count:
                break
            angle = rng.uniform(0, 2 * math.pi)
            dist  = rng.uniform(3, radius * 0.85)
            px    = int(cx + math.cos(angle) * dist)
            py    = int(cy + math.sin(angle) * dist)
            # Snap to tile grid, random size
            w = rng.randint(*PARCEL_W_RANGE)
            h = rng.randint(*PARCEL_H_RANGE)
            p = _try_place(px - w // 2, py - h // 2, w, h, t_idx)
            if p:
                parcels.append(p)
                placed += 1

    # Wilderness parcels
    wplaced = 0
    for _ in range(WILDERNESS_PARCELS * 6):
        if wplaced >= WILDERNESS_PARCELS:
            break
        x = rng.randint(10, WORLD_W - 25)
        y = rng.randint(10, WORLD_H - 15)
        w = rng.randint(PARCEL_W_RANGE[0], PARCEL_W_RANGE[1] - 3)
        h = rng.randint(PARCEL_H_RANGE[0], PARCEL_H_RANGE[1] - 2)
        p = _try_place(x, y, w, h, None)
        if p:
            parcels.append(p)
            wplaced += 1

    return parcels

# ---- Main entry point -------------------------------------------------------

async def generate_world_if_needed():
    """
    Called once at engine startup. Generates world content if not already done.
    Safe to call multiple times (idempotent via world_gen_state).
    """
    if await queries.world_is_generated():
        return

    rng = random.Random(42)   # deterministic seed — same world every fresh install

    print("[world_gen] Generating world...")

    towns    = _place_towns(rng)
    for t in towns:
        t["npc_district"] = place_npc_district(t, rng)
    nodes    = _generate_nodes(rng)
    parcels  = _generate_parcels(rng, towns, nodes)

    town_ids = await queries.insert_towns_bulk(towns)
    await queries.insert_nodes_bulk(nodes)
    await queries.insert_parcels_bulk(parcels, town_ids)

    await queries.mark_world_generated()
    print(f"[world_gen] Done. {len(towns)} towns, {len(nodes)} nodes, {len(parcels)} parcels.")
