"""
Procedural world generation.

Runs once at startup (guarded by world_gen_state.done). Generates:
  - 40 towns with organic, irregular polygon boundaries
  - resource nodes distributed by biome, plus clustered forest wood (tree variants)
  - ~700 land parcels of varying size and price
"""
import math
import random
import json
from server.game.constants import (
    WORLD_W, WORLD_H, MINERAL_NODE_TYPES,
    TOWN_ADJ, TOWN_NOUN, TOWN_COUNT, TOWN_MIN_DIST,
    TOWN_RADIUS_MIN, TOWN_RADIUS_MAX,
    PARCEL_W_RANGE, PARCEL_H_RANGE,
    PARCEL_PRICE_PER_TILE, PARCEL_RESOURCE_BONUS, PARCEL_MIN_PRICE,
    TOWN_PARCELS_PER_TOWN, WILDERNESS_PARCELS,
    PLAYER_SPAWN,
)
from server.game.town_npcs import place_npc_district
from server.game.terrain_features import generate_water_features, generate_poor_soil_for_parcels
from server.db import queries

# ---- Biome helpers ----------------------------------------------------------

def _biome(x: int, y: int) -> str:
    """
    Simple smooth biome from position. Returns one of:
    'forest', 'rocky', 'plains', 'wetland'

    Forest is widened (~40% of the map) so viewports usually include trees;
    remaining bands are tightened slightly.
    """
    nx, ny = x / 250, y / 250
    v = (math.sin(nx * 2.1) * math.cos(ny * 1.7) +
         math.cos(nx * 1.3 + ny * 0.9) + 2.0) / 4.0
    if v < 0.20: return "wetland"
    if v < 0.40: return "plains"
    if v < 0.80: return "forest"
    return "rocky"


BIOME_RESOURCES = {
    # Wood is placed in forest *clusters* (_add_forest_clusters), not on the generic grid,
    # so forests read as groves instead of a grid of identical nodes.
    "forest":  [("dirt",   50, 0.06)],
    "rocky":   [("stone",  120,  0.02), ("gravel", 100, 0.03)],
    "plains":  [("dirt",    60,  0.07), ("topsoil", 80, 0.40)],
    # Manure is a byproduct of player-built Stables — not a wild resource.
    # Compost is a byproduct of player-built Compost Heaps — not a wild resource.
    "wetland": [("clay",   100,  0.05), ("topsoil", 60, 0.15)],
}

# Sprinkled often enough that plains/wetland viewports still see stone/gravel/clay/dirt.
MINERAL_QUAD = [
    ("stone", 120, 0.02),
    ("gravel", 100, 0.03),
    ("clay", 100, 0.05),
    ("dirt", 60, 0.07),
]

# Wild trees (forest clusters) — more abundant than the old scattered forest wood nodes.
# Wood target ~6× prior cluster count; non-wood grid uses RESOURCE_GRID_STEP for ~3× density.
FOREST_WOOD_MAX = 118
FOREST_WOOD_REPLENISH = 0.085
FOREST_CLUSTER_TARGET = 880
FOREST_CLUSTER_MIN_SPACING = 8
MIN_TREES_PER_FOREST_CLUSTER = 3  # never commit a lone tree — smallest grove is 3 trees
# Denser grid + higher hit rate → typical screen has several nodes including minerals.
RESOURCE_GRID_STEP = 10
GRID_CELL_HIT_PROB = 0.48
# Small wood stands in plains/wetland (meadow copses) — viewports away from forest still have trees.
MEADOW_COPSE_TARGET = 200
MEADOW_COPSE_MIN_SPACING = 11


def _pick_resource_for_grid(rng: random.Random, biome: str) -> tuple:
    """
    Mostly biome-typical resources, but often enough any biome drops the four base minerals
    so a random window can show stone/gravel/clay/dirt without crossing the whole map.
    """
    if rng.random() < 0.30:
        return rng.choice(MINERAL_QUAD)
    return rng.choice(BIOME_RESOURCES[biome])

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

def _add_forest_clusters(
    rng: random.Random,
    nodes: list[dict],
    occupied: set[tuple[int, int]],
    sx: int,
    sy: int,
    near_spawn,
) -> None:
    """
    Place many wood nodes in forest biomes as irregular clusters (deciduous vs conifer stands).
    Each tree gets a tree_variant (0–7 deciduous shapes, 8–15 conifer shapes).
    """
    cluster_centers: list[tuple[int, int]] = []
    attempts = 0
    max_attempts = 300000
    while len(cluster_centers) < FOREST_CLUSTER_TARGET and attempts < max_attempts:
        attempts += 1
        cx = rng.randint(30, WORLD_W - 30)
        cy = rng.randint(30, WORLD_H - 30)
        if near_spawn(cx, cy):
            continue
        if _biome(cx, cy) != "forest":
            continue
        if any(
            math.hypot(cx - ox, cy - oy) < FOREST_CLUSTER_MIN_SPACING
            for ox, oy in cluster_centers
        ):
            continue

        kind = rng.randint(0, 1)  # 0 = deciduous stand, 1 = conifer stand
        radius = rng.randint(5, 9)
        n_trees = rng.randint(6, 14)
        batch: list[dict] = []
        placed = 0
        t_attempts = 0
        while placed < n_trees and t_attempts < n_trees * 30:
            t_attempts += 1
            dx = rng.randint(-radius, radius)
            dy = rng.randint(-radius, radius)
            if dx * dx + dy * dy > radius * radius:
                continue
            tx, ty = cx + dx, cy + dy
            if tx < 8 or tx >= WORLD_W - 8 or ty < 8 or ty >= WORLD_H - 8:
                continue
            if near_spawn(tx, ty):
                continue
            if _biome(tx, ty) != "forest":
                continue
            if (tx, ty) in occupied:
                continue
            variant = kind * 8 + rng.randint(0, 7)
            dist = math.hypot(tx - sx, ty - sy)
            freshness = max(0.42, 1.0 - dist / (WORLD_W * 0.52))
            max_a = FOREST_WOOD_MAX * rng.uniform(0.92, 1.08)
            rate = FOREST_WOOD_REPLENISH * rng.uniform(0.9, 1.1)
            batch.append({
                "x": tx,
                "y": ty,
                "node_type": "wood",
                "current_amount": round(max_a * rng.uniform(0.58, 0.92) * freshness, 1),
                "max_amount": round(max_a, 1),
                "replenish_rate": rate,
                "tree_variant": variant,
            })
            placed += 1

        if len(batch) >= MIN_TREES_PER_FOREST_CLUSTER:
            for n in batch:
                occupied.add((n["x"], n["y"]))
                nodes.append(n)
            cluster_centers.append((cx, cy))


def _add_meadow_copses(
    rng: random.Random,
    nodes: list[dict],
    occupied: set[tuple[int, int]],
    sx: int,
    sy: int,
    near_spawn,
) -> None:
    """
    Wood groves on plains and wetland (not forest — those use _add_forest_clusters).
    Keeps clustered trees; avoids lone stumps via MIN_TREES_PER_FOREST_CLUSTER.
    """
    cluster_centers: list[tuple[int, int]] = []
    attempts = 0
    max_attempts = 320000
    while len(cluster_centers) < MEADOW_COPSE_TARGET and attempts < max_attempts:
        attempts += 1
        cx = rng.randint(30, WORLD_W - 30)
        cy = rng.randint(30, WORLD_H - 30)
        if near_spawn(cx, cy):
            continue
        b = _biome(cx, cy)
        if b not in ("plains", "wetland"):
            continue
        if any(
            math.hypot(cx - ox, cy - oy) < MEADOW_COPSE_MIN_SPACING
            for ox, oy in cluster_centers
        ):
            continue

        kind = rng.randint(0, 1)
        radius = rng.randint(4, 7)
        n_trees = rng.randint(5, 11)
        batch: list[dict] = []
        placed = 0
        t_attempts = 0
        while placed < n_trees and t_attempts < n_trees * 35:
            t_attempts += 1
            dx = rng.randint(-radius, radius)
            dy = rng.randint(-radius, radius)
            if dx * dx + dy * dy > radius * radius:
                continue
            tx, ty = cx + dx, cy + dy
            if tx < 8 or tx >= WORLD_W - 8 or ty < 8 or ty >= WORLD_H - 8:
                continue
            if near_spawn(tx, ty):
                continue
            if _biome(tx, ty) not in ("plains", "wetland"):
                continue
            if (tx, ty) in occupied:
                continue
            variant = kind * 8 + rng.randint(0, 7)
            dist = math.hypot(tx - sx, ty - sy)
            freshness = max(0.42, 1.0 - dist / (WORLD_W * 0.52))
            max_a = FOREST_WOOD_MAX * rng.uniform(0.92, 1.08)
            rate = FOREST_WOOD_REPLENISH * rng.uniform(0.9, 1.1)
            batch.append({
                "x": tx,
                "y": ty,
                "node_type": "wood",
                "current_amount": round(max_a * rng.uniform(0.58, 0.92) * freshness, 1),
                "max_amount": round(max_a, 1),
                "replenish_rate": rate,
                "tree_variant": variant,
            })
            placed += 1

        if len(batch) >= MIN_TREES_PER_FOREST_CLUSTER:
            for n in batch:
                occupied.add((n["x"], n["y"]))
                nodes.append(n)
            cluster_centers.append((cx, cy))


def _generate_nodes(rng: random.Random) -> list[dict]:
    """
    Scatter ~1500+ resource nodes across the world by biome (dense grid), plus clustered forest wood.
    Near spawn (±35 tiles) is always seeded with starter resources.
    """
    nodes: list[dict] = []
    occupied: set[tuple[int, int]] = set()
    sx, sy = PLAYER_SPAWN

    # Guaranteed starter resources — placed near the NPC shops (50-70 tiles from spawn)
    # so new players have to travel a bit to find them.
    # Only truly wild resources here: wood, stone, gravel, clay, topsoil, dirt.
    # Manure (from Stable) and compost (from Compost Heap) are never wild.
    # Starter wood: two 3-tree groves (never lone trees) near the NPC shop ring.
    for (cx, cy), tv0 in [
        ((sx - 55, sy - 8), 3),
        ((sx + 52, sy - 8), 11),
    ]:
        for i, (dx, dy) in enumerate([(0, 0), (1, 0), (0, -1)]):
            x, y = cx + dx, cy + dy
            occupied.add((x, y))
            nodes.append({
                "x": x, "y": y, "node_type": "wood",
                "current_amount": round(100 * 0.8, 1),
                "max_amount": 100, "replenish_rate": 0.07,
                "tree_variant": (tv0 + i) % 16,
            })

    for x, y, rtype, max_a, rate, tv in [
        (sx - 52, sy + 5,  "stone",  120, 0.02, 0),
        (sx + 55, sy + 5,  "gravel", 100, 0.03, 0),
        (sx - 50, sy + 10, "gravel", 100, 0.03, 0),
        (sx + 50, sy + 10, "clay",   100, 0.05, 0),
        (sx - 5,  sy - 58, "topsoil", 80, 0.40, 0),
        (sx + 8,  sy - 55, "stone",  120, 0.02, 0),
        (sx - 5,  sy + 55, "clay",   100, 0.05, 0),
        (sx + 8,  sy + 58, "dirt",    60, 0.07, 0),
    ]:
        occupied.add((x, y))
        nodes.append({
            "x": x, "y": y, "node_type": rtype,
            "current_amount": round(max_a * 0.8, 1),
            "max_amount": max_a, "replenish_rate": rate,
            "tree_variant": tv,
        })

    # Protected zone: keep the spawn tile clear so players start on an empty field
    def near_spawn(x, y):
        return abs(x - sx) <= 35 and abs(y - sy) <= 35

    _add_forest_clusters(rng, nodes, occupied, sx, sy, near_spawn)
    _add_meadow_copses(rng, nodes, occupied, sx, sy, near_spawn)

    # Grid scatter: dense step + hit probability; minerals often from MINERAL_QUAD (see _pick_resource_for_grid)
    for gx in range(0, WORLD_W, RESOURCE_GRID_STEP):
        for gy in range(0, WORLD_H, RESOURCE_GRID_STEP):
            if rng.random() > GRID_CELL_HIT_PROB:
                continue
            x = gx + rng.randint(0, RESOURCE_GRID_STEP - 1)
            y = gy + rng.randint(0, RESOURCE_GRID_STEP - 1)
            x = max(5, min(WORLD_W - 5, x))
            y = max(5, min(WORLD_H - 5, y))
            if near_spawn(x, y):
                continue
            if (x, y) in occupied:
                continue

            biome = _biome(x, y)
            rtype, max_a, rate = _pick_resource_for_grid(rng, biome)

            # Farther from spawn → lower current amount (depleted over time)
            dist      = math.hypot(x - sx, y - sy)
            freshness = max(0.3, 1.0 - dist / (WORLD_W * 0.6))

            occupied.add((x, y))
            nodes.append({
                "x": x, "y": y, "node_type": rtype,
                "current_amount": round(max_a * 0.5 * freshness, 1),
                "max_amount": max_a, "replenish_rate": rate,
                "tree_variant": 0,
            })

    _boost_mineral_nodes(rng, nodes, occupied, sx, sy, near_spawn)

    return nodes


def _boost_mineral_nodes(
    rng: random.Random,
    nodes: list[dict],
    occupied: set[tuple[int, int]],
    sx: int,
    sy: int,
    near_spawn,
) -> None:
    """Extra stone/gravel/clay/dirt; often uses MINERAL_QUAD so every biome gets base minerals."""
    count = sum(1 for n in nodes if n["node_type"] in MINERAL_NODE_TYPES)
    extra = int(count * 2.1)
    placed = 0
    attempts = 0
    while placed < extra and attempts < max(extra * 50, 8000):
        attempts += 1
        x = rng.randint(8, WORLD_W - 9)
        y = rng.randint(8, WORLD_H - 9)
        if near_spawn(x, y):
            continue
        if (x, y) in occupied:
            continue
        biome = _biome(x, y)
        opts = [o for o in BIOME_RESOURCES[biome] if o[0] in MINERAL_NODE_TYPES]
        if rng.random() < 0.55 or len(opts) < 2:
            opts = MINERAL_QUAD
        if not opts:
            opts = MINERAL_QUAD
        rtype, max_a, rate = rng.choice(opts)
        dist = math.hypot(x - sx, y - sy)
        freshness = max(0.3, 1.0 - dist / (WORLD_W * 0.6))
        occupied.add((x, y))
        nodes.append({
            "x": x, "y": y, "node_type": rtype,
            "current_amount": round(max_a * 0.5 * freshness, 1),
            "max_amount": max_a, "replenish_rate": rate,
            "tree_variant": 0,
        })
        placed += 1

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


def densify_nodes_for_existing_world(
    rng: random.Random,
    occupied: set[tuple[int, int]],
) -> list[dict]:
    """
    Add wild nodes on top of an existing world (migration): meadow copses + grid + mineral boost
    on tiles not in ``occupied``. Does not add forest-cluster groves (avoids doubling forest density).
    Caller inserts rows with queries.insert_nodes_bulk.
    """
    sx, sy = PLAYER_SPAWN

    def near_spawn(x, y):
        return abs(x - sx) <= 35 and abs(y - sy) <= 35

    occ = set(occupied)
    nodes: list[dict] = []
    _add_meadow_copses(rng, nodes, occ, sx, sy, near_spawn)
    for gx in range(0, WORLD_W, RESOURCE_GRID_STEP):
        for gy in range(0, WORLD_H, RESOURCE_GRID_STEP):
            if rng.random() > GRID_CELL_HIT_PROB:
                continue
            x = gx + rng.randint(0, RESOURCE_GRID_STEP - 1)
            y = gy + rng.randint(0, RESOURCE_GRID_STEP - 1)
            x = max(5, min(WORLD_W - 5, x))
            y = max(5, min(WORLD_H - 5, y))
            if near_spawn(x, y):
                continue
            if (x, y) in occ:
                continue
            biome = _biome(x, y)
            rtype, max_a, rate = _pick_resource_for_grid(rng, biome)
            dist = math.hypot(x - sx, y - sy)
            freshness = max(0.3, 1.0 - dist / (WORLD_W * 0.6))
            occ.add((x, y))
            nodes.append({
                "x": x, "y": y, "node_type": rtype,
                "current_amount": round(max_a * 0.5 * freshness, 1),
                "max_amount": max_a, "replenish_rate": rate,
                "tree_variant": 0,
            })
    _boost_mineral_nodes(rng, nodes, occ, sx, sy, near_spawn)
    return nodes


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

    await queries.ensure_terrain_tables()
    node_pos = {(n["x"], n["y"]) for n in nodes}
    water = generate_water_features(rng, node_pos, towns)
    await queries.insert_water_tiles_bulk(water)
    poor = generate_poor_soil_for_parcels(rng, parcels)
    await queries.insert_poor_soil_bulk(poor)

    await queries.mark_world_generated()
    print(
        f"[world_gen] Done. {len(towns)} towns, {len(nodes)} nodes, {len(parcels)} parcels, "
        f"{len(water)} water tiles (ponds, streams, major rivers), {len(poor)} poor-soil tiles.",
    )
