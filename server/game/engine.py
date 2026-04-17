"""
In-memory game state. All mutation happens here; the DB handles persistence.

v0.9.0: water/bridges/poor soil, cancel/demolish, mineral boost; v0.8.0: broken-handle half capacity;
v0.7.0: staged construction, silos, winter spoilage;
worlds are 1000×1000;
towns have polygon boundaries; transactions carry town taxes.
"""
import asyncio
import datetime
import json
import math
import random
import time
import uuid
from typing import Optional

from fastapi import WebSocket

from server.game.constants import (
    WORLD_W, WORLD_H, COLLECTION_RADIUS, COLLECTION_RATE, COLLECTION_RATES,
    PILE_COLLECTION_MULT,
    ROAD_GROWTH_TILES_MIN, ROAD_GROWTH_TILES_MAX,
    MARKET_TILE, STRUCTURE_DEFS, MARKET_BASE_PRICES, WINTER_PILE_SPOIL_TYPES,
    BRIDGE_COIN_COST, BRIDGE_WOOD_REQUIRED, DEMOLISH_REFUND_RATE,
    MARKET_DRIFT_INTERVAL, MARKET_DRIFT_THRESHOLD,
    NPC_SHOP_LOCATIONS, NPC_SHOP_LABELS, NPC_SHOP_ADJACENCY,
    SEED_SHOP_ITEMS, CROP_DEFS,
    WB_BUCKET_CAP, WB_BUCKET_COST, WB_TIRE_FLAT_MULT, WB_TIRE_COST,
    WB_HANDLE_BREAK_MULT, WB_HANDLE_COST, WB_BARROW_DECAY_MULT, WB_BARROW_COST,
    REPAIR_COST_PER_PCT, REPAIR_FLAT_COST, UPGRADE_COMPONENTS,
    MAX_TAX_RATE, ELECTION_CYCLE_DAYS, VOTING_WINDOW_HOURS,
    VIEWPORT_RADIUS,
)
from server.game.seasons import SeasonClock
from server.game.wb_condition import (
    apply_move_decay,
    effective_bucket_cap,
    trim_bucket_to_effective_cap,
)
from server.game.town_npcs import (
    place_npc_district,
    parse_npc_district,
    district_spread_ok,
    DISTRICT_KEYS,
)
from server.game.roads_util import path_union_for_sites, pick_adjacent_growth_tile
from server.game.construction import (
    init_construction_state,
    deposit_all_from_bucket,
    construction_is_complete,
    foundation_remaining,
    building_remaining,
)
from server.db import queries


def _bucket_total(bucket: dict) -> float:
    return sum(bucket.values())


def _migrate_pocket_fertilizer_to_bucket(player: dict) -> None:
    """Fertilizer is carried in the wheelbarrow; move legacy pocket stock into the bucket."""
    pocket = player.setdefault("pocket", {})
    raw = pocket.pop("fertilizer", None)
    if raw is None:
        return
    try:
        amt = max(0.0, float(raw))
    except (TypeError, ValueError):
        return
    if amt <= 0:
        return
    cap = effective_bucket_cap(player) - _bucket_total(player.get("bucket", {}))
    move = min(amt, cap)
    if move <= 0:
        pocket["fertilizer"] = amt
        return
    b = player.setdefault("bucket", {})
    b["fertilizer"] = round(b.get("fertilizer", 0) + move, 2)
    rest = amt - move
    if rest > 0:
        pocket["fertilizer"] = rest


def _near_shop(player: dict, shop_key: str, towns: dict[int, dict]) -> bool:
    px, py = player["x"], player["y"]
    for town in towns.values():
        d = town.get("npc_district")
        if not d:
            continue
        pos = d.get(shop_key)
        if not pos or len(pos) < 2:
            continue
        sx, sy = int(pos[0]), int(pos[1])
        if abs(px - sx) <= NPC_SHOP_ADJACENCY and abs(py - sy) <= NPC_SHOP_ADJACENCY:
            return True
    if shop_key in NPC_SHOP_LOCATIONS:
        sx, sy = NPC_SHOP_LOCATIONS[shop_key]
        if abs(px - sx) <= NPC_SHOP_ADJACENCY and abs(py - sy) <= NPC_SHOP_ADJACENCY:
            return True
    return False


def _at_any_npc_market(player: dict, towns: dict[int, dict]) -> bool:
    px, py = player["x"], player["y"]
    for town in towns.values():
        d = town.get("npc_district") or {}
        m = d.get("market")
        if m and len(m) >= 2 and px == int(m[0]) and py == int(m[1]):
            return True
    return (px, py) == MARKET_TILE

def _dir_offset(direction: str) -> tuple[int, int]:
    return {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(
        (direction or "down").lower(), (0, 1),
    )


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


class GameEngine:
    def __init__(self):
        self.players:    dict[int, dict]     = {}
        self.sockets:    dict[int, WebSocket] = {}
        self.tokens:     dict[str, int]      = {}
        self.nodes:      dict[int, dict]     = {}    # resource nodes
        self.structures: dict[int, dict]     = {}    # player structures
        # World parcels: id -> parcel; parcel_at: (x,y) -> parcel_id
        self.world_parcels: dict[int, dict]  = {}
        self.parcel_at:     dict[tuple, int] = {}
        # Towns: id -> town
        self.towns: dict[int, dict]          = {}
        self.town_bans: dict[int, dict]      = {}    # town_id -> {structures, goods}
        # Piles: (x,y) -> {rtype -> pile_dict}
        self.piles: dict[tuple, dict[str, dict]] = {}
        # Crops: (x,y) -> crop_dict
        self.crops: dict[tuple, dict] = {}
        # Soil: (x,y) -> 1 tilled (ready for seeds), 0 untilled / needs till
        self.soil: dict[tuple[int, int], int] = {}
        self.road_tiles: set[tuple[int, int]] = set()
        self.water_tiles: set[tuple[int, int]] = set()
        self.bridge_tiles: set[tuple[int, int]] = set()
        self.poor_soil: set[tuple[int, int]] = set()
        self.bridge_progress: dict[tuple[int, int], dict] = {}
        self.prices: dict[str, float] = {}
        self.sales_volume: dict[str, float] = {r: 0.0 for r in MARKET_BASE_PRICES}
        self.season = SeasonClock()

        self._last_resource_tick = time.monotonic()
        self._last_persist       = time.monotonic()
        self._last_market_drift  = time.monotonic()
        self._last_election_check = time.monotonic()

    # ------------------------------------------------------------------ load

    async def load(self):
        await queries.ensure_resource_nodes_tree_variant()
        # World generation first (no-op if already done)
        from server.game.world_gen import generate_world_if_needed
        await generate_world_if_needed()

        await queries.ensure_towns_npc_district_column()

        # Load towns + clustered NPC districts (backfill if missing)
        for t in await queries.load_all_towns():
            self.towns[t["id"]] = dict(t)
        npc_district_rebuilt: set[int] = set()
        for tid, town in list(self.towns.items()):
            parsed = parse_npc_district(town.get("npc_district"))
            if parsed and district_spread_ok(parsed):
                town["npc_district"] = parsed
                continue
            # Missing district, or legacy DB layout (shops touching / 2×2) — re-place and persist
            rng = random.Random(tid * 1103515245 + 12345)
            d = place_npc_district(town, rng)
            town["npc_district"] = d
            await queries.update_town_npc_district(tid, d)
            npc_district_rebuilt.add(tid)

        # Load parcels and build spatial index
        for p in await queries.load_all_parcels():
            p = dict(p)
            self.world_parcels[p["id"]] = p
            for dx in range(p["w"]):
                for dy in range(p["h"]):
                    self.parcel_at[(p["x"] + dx, p["y"] + dy)] = p["id"]

        # Load other entities
        for node in await queries.load_all_nodes():
            self.nodes[node["id"]] = dict(node)
        for struct in await queries.load_all_structures():
            self.structures[struct["id"]] = self._struct_to_node(struct)
        for pile in await queries.load_all_piles():
            key = (pile["x"], pile["y"])
            self.piles.setdefault(key, {})[pile["resource_type"]] = dict(pile)
        await queries.ensure_crop_winter_dead_column()
        await queries.ensure_soil_tiles_table()
        await queries.cleanup_legacy_harvested_crop_rows()
        for row in await queries.load_all_soil_tiles():
            self.soil[(int(row["x"]), int(row["y"]))] = int(row["tilled"])
        for crop in await queries.load_all_crops():
            self.crops[(crop["x"], crop["y"])] = dict(crop)

        await queries.ensure_terrain_tables()
        if await queries.count_water_tiles() == 0 and await queries.world_is_generated():
            from server.game.terrain_features import generate_water_features, generate_poor_soil_for_parcels

            rng = random.Random(991)
            node_pos = {(n["x"], n["y"]) for n in self.nodes.values()}
            water = generate_water_features(rng, node_pos, list(self.towns.values()))
            await queries.insert_water_tiles_bulk(water)
            self.water_tiles = set(water)
            poor = generate_poor_soil_for_parcels(rng, list(self.world_parcels.values()))
            await queries.insert_poor_soil_bulk(poor)
            self.poor_soil = set(poor)
        else:
            self.water_tiles = set(await queries.load_all_water_tiles())
            self.poor_soil = set(await queries.load_all_poor_soil_tiles())
        self.bridge_tiles = set(await queries.load_all_bridge_tiles())
        self.bridge_progress = {}
        for row in await queries.load_all_bridge_progress():
            self.bridge_progress[(int(row["x"]), int(row["y"]))] = {
                "wood_deposited": float(row["wood_deposited"]),
                "coins_paid": int(row["coins_paid"]),
            }

        await queries.ensure_world_roads_table()
        await queries.migrate_resource_piles_parcel_optional()
        self.road_tiles = set(await queries.load_all_roads())
        if not self.road_tiles:
            await self._seed_initial_npc_roads()
        for tid in npc_district_rebuilt:
            t = self.towns.get(tid)
            if t:
                await self._merge_npc_roads_for_town(t)

        await queries.ensure_market_price_rows(MARKET_BASE_PRICES)
        self.prices = await queries.get_market_prices()
        for rtype, base in MARKET_BASE_PRICES.items():
            if rtype not in self.prices:
                self.prices[rtype] = base
        self.town_bans = await queries.load_town_bans()

        season_row = await queries.load_season_state()
        if season_row:
            self.season.load_from_db(season_row["season"], season_row["season_start"])

    def _struct_to_node(self, struct: dict) -> dict:
        sdef = STRUCTURE_DEFS.get(struct["structure_type"], {})
        cfg = struct.get("config") or {}
        if isinstance(cfg, str):
            cfg = json.loads(cfg)
        inv = struct.get("inventory") or {}
        if isinstance(inv, str):
            inv = json.loads(inv)
        cons = cfg.get("construction")
        construction_active = bool(cons)
        node = {
            "id":             struct["id"],
            "x":              struct["x"],
            "y":              struct["y"],
            "node_type":      sdef.get("produces") or struct["structure_type"],
            "structure_type": struct["structure_type"],
            "current_amount": 0.0,
            "max_amount":     0 if construction_active else sdef.get("max_amount", 0),
            "replenish_rate": 0 if construction_active else sdef.get("replenish_rate", 0),
            "collect_fee":    0 if construction_active else sdef.get("collect_fee", 0),
            "owner_id":       struct["owner_id"],
            "owner_name":     struct["owner_name"],
            "is_structure":   True,
            "is_market":      False if construction_active else sdef.get("is_market", False),
            "is_town_hall":   False if construction_active else sdef.get("is_town_hall", False),
            "is_silo":        bool(sdef.get("is_silo")) and not construction_active,
            "construction_active": construction_active,
            "inventory":      inv,
            "config":         cfg,
        }
        return node

    async def _seed_initial_npc_roads(self):
        """First boot: dirt paths inside each town polygon linking NPC district sites."""
        new_tiles: set[tuple[int, int]] = set()
        for town in self.towns.values():
            poly = town.get("boundary") or []
            d = town.get("npc_district") or {}
            if len(poly) < 3:
                continue
            sites: list[tuple[int, int]] = []
            for k in DISTRICT_KEYS:
                v = d.get(k)
                if v and len(v) >= 2:
                    sites.append((int(v[0]), int(v[1])))
            if len(sites) >= 2:
                new_tiles |= path_union_for_sites(poly, sites, set())
        self.road_tiles |= new_tiles
        if new_tiles:
            await queries.insert_road_bulk(list(new_tiles))

    async def _merge_npc_roads_for_town(self, town: dict):
        """After npc_district moves, extend dirt paths to the new shop sites (INSERT IGNORE duplicates)."""
        poly = town.get("boundary") or []
        d = town.get("npc_district") or {}
        if len(poly) < 3:
            return
        sites: list[tuple[int, int]] = []
        for k in DISTRICT_KEYS:
            v = d.get(k)
            if v and len(v) >= 2:
                sites.append((int(v[0]), int(v[1])))
        if len(sites) < 2:
            return
        new_tiles = path_union_for_sites(poly, sites, set())
        extra = new_tiles - self.road_tiles
        self.road_tiles |= new_tiles
        if extra:
            await queries.insert_road_bulk(list(extra))

    def _structure_footprint_tiles(self) -> set[tuple[int, int]]:
        return {(int(n["x"]), int(n["y"])) for n in self.structures.values()}

    def _structure_tile_touches_road(self, sx: int, sy: int) -> bool:
        for rx, ry in self.road_tiles:
            if abs(rx - sx) + abs(ry - sy) == 1:
                return True
        return False

    async def _kill_unharvested_crops_for_winter(self):
        alive = [c for c in self.crops.values() if not c.get("winter_dead")]
        if not alive:
            return
        await queries.mark_all_crops_winter_dead()
        for key, c in list(self.crops.items()):
            if not c.get("winter_dead"):
                c["winter_dead"] = 1
        await self._broadcast_all({
            "type": "notice",
            "msg": "Winter — crops in the field froze. Till the soil to clear them, then plant again. "
                   "Uncovered wheat piles rot; grain in a silo is safe.",
        })

    async def _winter_rot_piles(self):
        """Convert vulnerable pile contents (e.g. wheat) to compost on the same tile."""
        rotted_tiles = 0
        for (tx, ty), pile_map in list(self.piles.items()):
            for rtype in list(pile_map.keys()):
                if rtype not in WINTER_PILE_SPOIL_TYPES:
                    continue
                pile = pile_map[rtype]
                amt = float(pile.get("amount", 0) or 0)
                if amt <= 0:
                    continue
                parcel_id = pile.get("parcel_id")
                owner_id = pile.get("owner_id")
                await queries.delete_pile(tx, ty, rtype)
                del pile_map[rtype]
                comp = pile_map.get("compost")
                prev = float(comp.get("amount", 0) or 0) if comp else 0.0
                new_amt = round(prev + amt, 2)
                sp = comp.get("sell_price") if comp else None
                row = await queries.upsert_pile(
                    parcel_id, owner_id, tx, ty, "compost", new_amt, sp,
                )
                pile_map["compost"] = dict(row)
                rotted_tiles += 1
            if not pile_map:
                del self.piles[(tx, ty)]
        if rotted_tiles:
            await self._broadcast_all({
                "type": "notice",
                "msg": "Winter — uncovered wheat piles have rotted into compost where they lay.",
            })

    def _soil_ready_for_planting(self, tx: int, ty: int) -> bool:
        return self.soil.get((tx, ty), 0) == 1

    async def _grow_roads_new_year(self):
        """Each spring: add a few dirt tiles extending toward player structures not yet by a road."""
        blocked = self._structure_footprint_tiles()
        budget = random.randint(ROAD_GROWTH_TILES_MIN, ROAD_GROWTH_TILES_MAX)
        added: list[tuple[int, int]] = []
        for _ in range(budget):
            goals = [
                (int(n["x"]), int(n["y"]))
                for n in self.structures.values()
                if not self._structure_tile_touches_road(int(n["x"]), int(n["y"]))
            ]
            if not goals:
                break
            random.shuffle(goals)
            goal = goals[0]
            ntile = pick_adjacent_growth_tile(
                self.road_tiles, goal, blocked, WORLD_W, WORLD_H,
            )
            if ntile is None:
                break
            self.road_tiles.add(ntile)
            added.append(ntile)
        if added:
            await queries.insert_road_bulk(added)

    def _player_can_free_pick_pile(self, player: dict, pile: dict) -> bool:
        """Timed pickup into barrow without going through buy flow."""
        pid = player["id"]
        if pile.get("sell_price") is not None:
            return pile.get("owner_id") == pid
        px, py = int(pile["x"]), int(pile["y"])
        par_id = self.parcel_at.get((px, py))
        par = self.world_parcels.get(par_id) if par_id else None
        if par and par.get("owner_id") is not None and par["owner_id"] == pile.get("owner_id"):
            return pid == pile.get("owner_id")
        return True

    # ---------------------------------------------------------------- helpers

    def _get_player_parcel(self, player: dict) -> Optional[dict]:
        pid = self.parcel_at.get((player["x"], player["y"]))
        return self.world_parcels.get(pid) if pid else None

    def _parcel_owning_tile(self, x: int, y: int) -> Optional[dict]:
        pid = self.parcel_at.get((x, y))
        return self.world_parcels.get(pid) if pid else None

    def _terrain_allows_move(self, x: int, y: int) -> bool:
        return (x, y) not in self.water_tiles

    def _get_player_town(self, player: dict) -> Optional[dict]:
        """Return the town the player is currently in, or None."""
        x, y = player["x"], player["y"]
        for town in self.towns.values():
            if _point_in_polygon(x, y, town["boundary"]):
                return town
        return None

    def _town_tax_rate(self, x: int, y: int) -> tuple[float, Optional[dict]]:
        """Return (tax_rate, town) for a tile. Returns (0.0, None) if no town."""
        for town in self.towns.values():
            if town.get("hall_built") and _point_in_polygon(x, y, town["boundary"]):
                return float(town.get("tax_rate", 0)), town
        return 0.0, None

    def _apply_town_tax(self, amount: int, x: int, y: int) -> tuple[int, int]:
        """
        Returns (after_tax_amount, tax_collected).
        Updates town treasury in-memory.
        """
        tax_rate, town = self._town_tax_rate(x, y)
        if tax_rate <= 0 or town is None:
            return amount, 0
        tax = int(amount * tax_rate)
        after = amount - tax
        town["treasury"] = town.get("treasury", 0) + tax
        return after, tax

    # ---------------------------------------------------------------- sessions

    def create_session(self, player: dict) -> str:
        token = str(uuid.uuid4())
        self.tokens[token] = player["id"]
        player.setdefault("pocket",          {})
        player.setdefault("bucket",         {})
        player.setdefault("wb_paint",        100.0)
        player.setdefault("wb_tire",         100.0)
        player.setdefault("wb_handle",       100.0)
        player.setdefault("wb_barrow",       100.0)
        player.setdefault("flat_tire",       0)
        player.setdefault("wb_bucket_level", 1)
        player.setdefault("wb_tire_level",   1)
        player.setdefault("wb_handle_level", 1)
        player.setdefault("wb_barrow_level", 1)
        player["bucket_cap"] = WB_BUCKET_CAP.get(player["wb_bucket_level"], 10)
        _migrate_pocket_fertilizer_to_bucket(player)
        trim_bucket_to_effective_cap(player)
        self.players[player["id"]] = player
        return token

    def get_player_by_token(self, token: str) -> Optional[dict]:
        pid = self.tokens.get(token)
        return self.players.get(pid) if pid else None

    def add_socket(self, player_id: int, ws: WebSocket):
        self.sockets[player_id] = ws

    async def remove_player(self, player_id: int):
        self.sockets.pop(player_id, None)
        player = self.players.get(player_id)
        if player:
            await queries.save_player(player)

    # ---------------------------------------------------------------- input

    async def handle_input(self, player_id: int, msg: dict):
        t = msg.get("type")
        if   t == "move":           self._move(player_id, msg.get("dir"))
        elif t == "sell":           await self._sell_npc_market(player_id)
        elif t == "buy_parcel":     await self._buy_parcel(player_id, msg.get("parcel_id"))
        elif t == "build":          await self._build(player_id, msg.get("structure_type"))
        elif t == "unload":         await self._unload(player_id)
        elif t == "deposit_build": await self._deposit_construction(player_id)
        elif t == "silo_withdraw": await self._silo_withdraw(player_id)
        elif t == "set_pile_price": await self._set_pile_price(player_id, msg.get("resource_type"), msg.get("price"))
        elif t == "buy_pile":       await self._buy_pile(player_id, msg.get("resource_type"), msg.get("amount"))
        elif t == "npc_shop_buy":   await self._npc_shop_buy(player_id, msg.get("shop"), msg.get("item"))
        elif t == "repair":         await self._repair(player_id, msg.get("component"))
        elif t == "upgrade_wb":     await self._upgrade_wb(player_id, msg.get("component"))
        elif t == "farm":           await self._farm(player_id)
        elif t == "market_config":  await self._market_config(player_id, msg.get("prices"))
        elif t == "market_trade":   await self._market_trade(player_id, msg.get("action"), msg.get("resource_type"), msg.get("amount"))
        elif t == "town_action":    await self._town_action(player_id, msg)
        elif t == "vote":           await self._vote(player_id, msg.get("candidate_id"))
        elif t == "cancel_construction": await self._cancel_construction(player_id)
        elif t == "demolish_structure":  await self._demolish_structure(player_id)
        elif t == "improve_soil":       await self._improve_soil(player_id)
        elif t == "fill_water":        await self._fill_water(player_id, msg.get("dir"))
        elif t == "bridge_deposit":    await self._bridge_deposit(player_id, msg.get("dir"))

    # ---- movement -----------------------------------------------------------

    def _move(self, player_id: int, direction: str):
        player = self.players.get(player_id)
        if not player:
            return
        dx, dy = {"up": (0,-1), "down": (0,1), "left": (-1,0), "right": (1,0)}.get(direction, (0,0))
        if dx == 0 and dy == 0:
            return
        nx, ny = player["x"] + dx, player["y"] + dy
        if not (0 <= nx < WORLD_W and 0 <= ny < WORLD_H):
            return
        if not self._terrain_allows_move(nx, ny):
            asyncio.ensure_future(self._send(player_id, {"type": "notice", "msg": "Water blocks the way — fill it on your land ([L]) or build a bridge ([J]) over it."}))
            return
        player["x"], player["y"] = nx, ny
        events = apply_move_decay(player)
        for ev in events:
            if ev == "flat_tire":
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": "Flat tyre! Movement is slower. Find the Repair Shop."}))
            elif ev == "handle_break":
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": "Handle snapped! You can only haul half capacity until you repair it at the Repair Shop."}))
            elif ev.startswith("spill:"):
                _, rtype, amt = ev.split(":")
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": f"Hole in barrow — spilled {amt} {rtype}!"}))
            elif ev.startswith("overspill:"):
                _, rtype, amt = ev.split(":")
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": f"Broken handle — dropped {amt} {rtype} (half capacity until you repair the handle)."}))

    # ---- NPC market ---------------------------------------------------------

    async def _sell_npc_market(self, player_id: int):
        player = self.players.get(player_id)
        if not player or not _at_any_npc_market(player, self.towns):
            return
        bucket = player.get("bucket", {})
        if not bucket:
            return
        earned = 0.0
        for rtype, amount in bucket.items():
            price = self.prices.get(rtype, 0)
            earned += amount * price
            self.sales_volume[rtype] = self.sales_volume.get(rtype, 0) + amount
        player["coins"] += int(earned)
        player["bucket"] = {}
        await self._send(player_id, {"type": "sold", "earned": int(earned), "coins": player["coins"]})

    # ---- buy parcel ---------------------------------------------------------

    async def _buy_parcel(self, player_id: int, parcel_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        parcel = self.world_parcels.get(parcel_id)
        if not parcel:
            await self._send(player_id, {"type": "notice", "msg": "No such parcel."})
            return
        if parcel.get("owner_id") is not None:
            await self._send(player_id, {"type": "notice", "msg": "That parcel is already owned."})
            return
        # Player must be standing on the parcel
        if self.parcel_at.get((player["x"], player["y"])) != parcel_id:
            await self._send(player_id, {"type": "notice", "msg": "Stand on the parcel to buy it."})
            return
        if player["coins"] < parcel["price"]:
            await self._send(player_id, {"type": "notice", "msg": f"Need {parcel['price']}c to buy this parcel."})
            return
        ok = await queries.buy_parcel(parcel_id, player_id, player["username"])
        if not ok:
            await self._send(player_id, {"type": "notice", "msg": "Someone else just bought it."})
            return
        player["coins"] -= parcel["price"]
        parcel["owner_id"]   = player_id
        parcel["owner_name"] = player["username"]
        await self._send(player_id, {
            "type":    "parcel_bought",
            "parcel":  self._parcel_wire(parcel),
            "coins":   player["coins"],
        })
        # Broadcast parcel update to all
        await self._broadcast_all({"type": "parcel_update", "parcel": self._parcel_wire(parcel)})

    # ---- build --------------------------------------------------------------

    async def _build(self, player_id: int, structure_type: str):
        player = self.players.get(player_id)
        if not player or structure_type not in STRUCTURE_DEFS:
            return
        parcel = self._get_player_parcel(player)
        if not parcel or parcel.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only build on your own land."})
            return

        town = self._get_player_town(player)
        if town:
            bans = self.town_bans.get(town["id"], {})
            if structure_type in bans.get("structures", set()):
                await self._send(player_id, {"type": "notice",
                    "msg": f"Building {structure_type} is banned in {town.get('custom_name') or town['name']}."})
                return

        tx, ty = player["x"], player["y"]
        if (tx, ty) in self.water_tiles:
            await self._send(player_id, {"type": "notice", "msg": "Can't build on water — fill it or bridge it first."})
            return
        for n in {**self.nodes, **self.structures}.values():
            if n["x"] == tx and n["y"] == ty:
                await self._send(player_id, {"type": "notice", "msg": "Something is already here."})
                return

        sdef = STRUCTURE_DEFS[structure_type]
        consdef = sdef.get("construction")
        if not consdef:
            await self._send(player_id, {"type": "notice", "msg": "Invalid structure definition."})
            return

        init_coins = int(consdef["init_coins"])
        if player["coins"] < init_coins:
            await self._send(player_id, {"type": "notice", "msg": f"Need {init_coins}c to start construction."})
            return

        if sdef.get("is_town_hall") and town and town.get("hall_built"):
            await self._send(player_id, {"type": "notice",
                "msg": f"{town.get('custom_name') or town['name']} already has a Town Hall."})
            return

        player["coins"] -= init_coins
        cfg = {"construction": init_construction_state(sdef)}
        struct_row = await queries.create_structure(
            parcel["id"], tx, ty, structure_type, config=cfg,
        )
        node = self._struct_to_node(struct_row)
        self.structures[node["id"]] = node
        await queries.save_player(player)

        await self._send(player_id, {
            "type":      "built",
            "structure": self._node_wire(node),
            "coins":     player["coins"],
            "msg":       f"Construction started — deposit stone/gravel for the foundation, then wood and other materials. [G] to deliver from your barrow.",
        })

    async def _deposit_construction(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        node = next(
            (n for n in self.structures.values() if n["x"] == tx and n["y"] == ty),
            None,
        )
        if not node or not node.get("construction_active"):
            await self._send(player_id, {"type": "notice", "msg": "No construction site here."})
            return
        if node.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Not your construction site."})
            return
        bucket = player.get("bucket", {})
        if not bucket:
            await self._send(player_id, {"type": "notice", "msg": "Barrow is empty."})
            return
        cons = node["config"].setdefault("construction", {})
        total, tags = deposit_all_from_bucket(cons, bucket)
        if total <= 0:
            await self._send(player_id, {"type": "notice",
                "msg": "Nothing in your barrow matches what's needed next (foundation first, then building)."})
            return
        await queries.save_structure(node)
        await queries.save_player(player)
        note = f"Delivered {round(total, 1)} units to the site."
        if "foundation_complete" in tags:
            note += " Foundation complete — keep supplying materials."
        if construction_is_complete(cons):
            await self._finalize_structure(node, player_id)
        else:
            await self._send(player_id, {
                "type": "notice", "msg": note,
                "structure": self._node_wire(node),
            })

    async def _finalize_structure(self, node: dict, player_id: int):
        sdef = STRUCTURE_DEFS.get(node["structure_type"], {})
        node["config"].pop("construction", None)
        node["construction_active"] = False
        node["replenish_rate"] = sdef.get("replenish_rate", 0)
        node["max_amount"] = sdef.get("max_amount", 0)
        node["collect_fee"] = sdef.get("collect_fee", 0)
        node["node_type"] = sdef.get("produces") or node["structure_type"]
        node["is_market"] = sdef.get("is_market", False)
        node["is_town_hall"] = sdef.get("is_town_hall", False)
        node["is_silo"] = bool(sdef.get("is_silo"))
        player = self.players.get(player_id)
        town = self._get_player_town(player) if player else None

        done_msg = f"{sdef.get('label', 'Building')} complete!"
        if sdef.get("is_town_hall") and town:
            town["hall_built"] = 1
            town["founder_id"] = player_id
            town["leader_id"] = player_id
            town["next_election_at"] = datetime.datetime.utcnow() + datetime.timedelta(days=ELECTION_CYCLE_DAYS)
            await queries.update_town(town)
            done_msg = (
                f"You founded {town.get('custom_name') or town['name']}! "
                "You can now set taxes and rename it."
            )
            await self._broadcast_all({"type": "town_update", "town": self._town_wire(town)})

        await queries.save_structure(node)
        await self._send(player_id, {
            "type":      "built",
            "structure": self._node_wire(node),
            "coins":     player["coins"] if player else 0,
            "msg":       done_msg,
        })

    async def _refund_materials_to_piles(
        self, player_id: int, tx: int, ty: int, materials: dict[str, float],
    ) -> None:
        if not materials:
            return
        pid_at = self.parcel_at.get((tx, ty))
        parcel = self.world_parcels.get(pid_at) if pid_at else None
        parcel_id = parcel["id"] if parcel else None
        key = (tx, ty)
        self.piles.setdefault(key, {})
        for rtype, amt in materials.items():
            try:
                a = float(amt)
            except (TypeError, ValueError):
                continue
            if a <= 0:
                continue
            existing = self.piles[key].get(rtype, {})
            new_amt = round(existing.get("amount", 0) + a, 2)
            pile_row = await queries.upsert_pile(
                parcel_id, player_id, tx, ty, rtype, new_amt, existing.get("sell_price"),
            )
            self.piles[key][rtype] = dict(pile_row)

    async def _cancel_construction(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        node = next((n for n in self.structures.values() if n["x"] == tx and n["y"] == ty), None)
        if not node or not node.get("construction_active"):
            await self._send(player_id, {"type": "notice", "msg": "No active construction site here."})
            return
        if node.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Not your construction site."})
            return
        cons = (node.get("config") or {}).get("construction") or {}
        deposited = cons.get("deposited") or {}
        sid = node["id"]
        await queries.delete_structure(sid)
        del self.structures[sid]
        refund = {k: float(v) for k, v in deposited.items() if float(v) > 0}
        await self._refund_materials_to_piles(player_id, tx, ty, refund)
        await self._send(player_id, {
            "type": "notice",
            "msg": "Construction cancelled — deposited materials returned to a pile here (init coins not refunded).",
        })

    async def _demolish_structure(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        node = next((n for n in self.structures.values() if n["x"] == tx and n["y"] == ty), None)
        if not node:
            await self._send(player_id, {"type": "notice", "msg": "Nothing built here."})
            return
        if node.get("construction_active"):
            await self._send(player_id, {"type": "notice", "msg": "Use cancel ([X]) while the site is under construction."})
            return
        if node.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Not your building."})
            return
        stype = node.get("structure_type")
        if stype == "town_hall":
            await self._send(player_id, {"type": "notice", "msg": "Town Hall can't be torn down."})
            return
        sdef = STRUCTURE_DEFS.get(stype or "", {})
        cons = sdef.get("construction") or {}
        fd = cons.get("foundation") or {}
        bd = cons.get("building") or {}
        refund: dict[str, float] = {}
        for k, v in {**fd, **bd}.items():
            try:
                req = float(v)
            except (TypeError, ValueError):
                continue
            if req <= 0:
                continue
            rate = float(DEMOLISH_REFUND_RATE.get(k, 0.5))
            amt = round(req * rate, 2)
            if amt > 0:
                refund[k] = refund.get(k, 0) + amt
        if node.get("is_silo"):
            inv = node.get("inventory") or {}
            w = float(inv.get("wheat", 0) or 0)
            if w > 0:
                refund["wheat"] = refund.get("wheat", 0) + w
        if node.get("is_market"):
            inv = node.get("inventory") or {}
            for k, v in inv.items():
                a = float(v or 0) * 0.5
                if a > 0:
                    refund[k] = refund.get(k, 0) + round(a, 2)
        sid = node["id"]
        await queries.delete_structure(sid)
        del self.structures[sid]
        await self._refund_materials_to_piles(player_id, tx, ty, refund)
        await self._send(player_id, {
            "type": "notice",
            "msg": "Building torn down — a partial refund was dropped in piles here (stone-heavy materials refund more than wood).",
        })

    async def _improve_soil(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        parcel = self._get_player_parcel(player)
        if not parcel or parcel.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Stand on your own land to improve soil."})
            return
        if (tx, ty) not in self.poor_soil:
            await self._send(player_id, {"type": "notice", "msg": "This tile doesn't need dirt."})
            return
        bucket = player.setdefault("bucket", {})
        if float(bucket.get("dirt", 0) or 0) < 1:
            await self._send(player_id, {"type": "notice", "msg": "Need at least 1 dirt in your barrow."})
            return
        bucket["dirt"] = round(bucket["dirt"] - 1, 2)
        if bucket["dirt"] <= 0:
            del bucket["dirt"]
        self.poor_soil.discard((tx, ty))
        await queries.delete_poor_soil_tile(tx, ty)
        await queries.save_player(player)
        await self._send(player_id, {"type": "notice", "msg": "Soil improved — you can till this tile now."})

    async def _fill_water(self, player_id: int, direction: str | None):
        player = self.players.get(player_id)
        if not player:
            return
        dx, dy = _dir_offset(direction or "down")
        px, py = player["x"], player["y"]
        wx, wy = px + dx, py + dy
        parcel = self._get_player_parcel(player)
        if not parcel or parcel.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Stand on your own land to landfill water next to you."})
            return
        wpar = self._parcel_owning_tile(wx, wy)
        if not wpar or wpar.get("id") != parcel.get("id") or wpar.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only fill water tiles on your own parcel."})
            return
        if (wx, wy) not in self.water_tiles:
            await self._send(player_id, {"type": "notice", "msg": "No water there."})
            return
        bucket = player.setdefault("bucket", {})
        if float(bucket.get("dirt", 0) or 0) < 1:
            await self._send(player_id, {"type": "notice", "msg": "Need 1 dirt in your barrow to fill this tile."})
            return
        bucket["dirt"] = round(bucket["dirt"] - 1, 2)
        if bucket["dirt"] <= 0:
            del bucket["dirt"]
        self.water_tiles.discard((wx, wy))
        await queries.delete_water_tile(wx, wy)
        await queries.save_player(player)
        await self._send(player_id, {"type": "notice", "msg": "Filled in water with dirt."})

    async def _bridge_deposit(self, player_id: int, direction: str | None):
        player = self.players.get(player_id)
        if not player:
            return
        dx, dy = _dir_offset(direction or "down")
        px, py = player["x"], player["y"]
        wx, wy = px + dx, py + dy
        if (wx, wy) not in self.water_tiles:
            await self._send(player_id, {"type": "notice", "msg": "No water in that direction."})
            return
        par = self._parcel_owning_tile(wx, wy)
        if par and par.get("owner_id") and par.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Can't build a bridge over another player's land."})
            return
        key = (wx, wy)
        prog = self.bridge_progress.get(key, {"wood_deposited": 0.0, "coins_paid": 0})
        wood_dep = float(prog.get("wood_deposited", 0) or 0)
        coins_paid = int(prog.get("coins_paid", 0) or 0)
        if not coins_paid:
            if player["coins"] < BRIDGE_COIN_COST:
                await self._send(player_id, {"type": "notice", "msg": f"Need {BRIDGE_COIN_COST}c to start this bridge section."})
                return
            player["coins"] -= BRIDGE_COIN_COST
            coins_paid = 1
        bucket = player.setdefault("bucket", {})
        wood_avail = float(bucket.get("wood", 0) or 0)
        need = max(0.0, BRIDGE_WOOD_REQUIRED - wood_dep)
        take = min(wood_avail, need)
        if take <= 0:
            await queries.save_player(player)
            await queries.upsert_bridge_progress(wx, wy, wood_dep, coins_paid)
            self.bridge_progress[key] = {"wood_deposited": wood_dep, "coins_paid": coins_paid}
            await self._send(player_id, {
                "type": "notice",
                "msg": f"Bridge site: {round(wood_dep, 1)}/{BRIDGE_WOOD_REQUIRED} wood — add wood from your barrow (facing the water tile).",
            })
            return
        bucket["wood"] = round(wood_avail - take, 2)
        if bucket["wood"] <= 0:
            del bucket["wood"]
        wood_dep = round(wood_dep + take, 2)
        await queries.save_player(player)
        if wood_dep >= BRIDGE_WOOD_REQUIRED:
            self.water_tiles.discard(key)
            await queries.delete_water_tile(wx, wy)
            self.bridge_tiles.add(key)
            await queries.insert_bridge_tile(wx, wy)
            await queries.delete_bridge_progress(wx, wy)
            self.bridge_progress.pop(key, None)
            await self._send(player_id, {"type": "notice", "msg": "Bridge complete — you can cross this tile."})
        else:
            await queries.upsert_bridge_progress(wx, wy, wood_dep, coins_paid)
            self.bridge_progress[key] = {"wood_deposited": wood_dep, "coins_paid": coins_paid}
            await self._send(player_id, {
                "type": "notice",
                "msg": f"Bridge: {round(wood_dep, 1)}/{BRIDGE_WOOD_REQUIRED} wood (need {round(BRIDGE_WOOD_REQUIRED - wood_dep, 1)} more).",
            })

    async def _silo_withdraw(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        node = next(
            (n for n in self.structures.values()
             if n.get("is_silo") and n["x"] == tx and n["y"] == ty and not n.get("construction_active")),
            None,
        )
        if not node or node.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Stand on your silo to withdraw grain."})
            return
        inv = node.setdefault("inventory", {})
        w = float(inv.get("wheat", 0) or 0)
        if w <= 0:
            await self._send(player_id, {"type": "notice", "msg": "Silo is empty."})
            return
        cap = effective_bucket_cap(player)
        load = _bucket_total(player.get("bucket", {}))
        space = cap - load
        if space <= 0:
            await self._send(player_id, {"type": "notice", "msg": "No space in barrow."})
            return
        take = min(w, space)
        take = round(take, 2)
        inv["wheat"] = round(w - take, 2)
        if inv["wheat"] <= 0:
            del inv["wheat"]
        player.setdefault("bucket", {})["wheat"] = round(player["bucket"].get("wheat", 0) + take, 2)
        await queries.save_structure(node)
        await queries.save_player(player)
        await self._send(player_id, {"type": "notice", "msg": f"Withdrew {take} wheat from the silo."})

    # ---- unload to pile -----------------------------------------------------

    async def _unload(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        bucket = player.get("bucket", {})
        if not bucket:
            await self._send(player_id, {"type": "notice", "msg": "Bucket is empty."})
            return
        tx, ty = player["x"], player["y"]
        silo = next(
            (
                n
                for n in self.structures.values()
                if n.get("is_silo")
                and int(n["x"]) == tx
                and int(n["y"]) == ty
                and not n.get("construction_active")
                and n.get("owner_id") == player_id
            ),
            None,
        )
        silo_put = 0.0
        if silo:
            sdef = STRUCTURE_DEFS.get("silo", {})
            cap = float(sdef.get("silo_capacity", 5000))
            inv = silo.setdefault("inventory", {})
            cur = float(inv.get("wheat", 0) or 0)
            space = max(0.0, cap - cur)
            w = float(bucket.get("wheat", 0) or 0)
            if w > 0 and space > 0:
                put = round(min(w, space), 2)
                inv["wheat"] = round(cur + put, 2)
                bucket["wheat"] = round(w - put, 2)
                if bucket["wheat"] <= 0:
                    del bucket["wheat"]
                silo_put = put
                await queries.save_structure(silo)
        if not bucket:
            await queries.save_player(player)
            await self._send(player_id, {
                "type": "notice",
                "msg": f"Stored {round(silo_put, 1)} wheat in the silo.",
            })
            return

        pid_at = self.parcel_at.get((tx, ty))
        parcel = self.world_parcels.get(pid_at) if pid_at else None
        parcel_id = parcel["id"] if parcel else None
        key = (tx, ty)
        self.piles.setdefault(key, {})
        total = 0.0
        for rtype, amt in list(bucket.items()):
            if amt <= 0:
                continue
            existing = self.piles[key].get(rtype, {})
            new_amt = round(existing.get("amount", 0) + amt, 2)
            pile_row = await queries.upsert_pile(
                parcel_id, player_id, tx, ty, rtype, new_amt, existing.get("sell_price"),
            )
            self.piles[key][rtype] = dict(pile_row)
            total += amt
        player["bucket"] = {}
        await queries.save_player(player)
        parts = []
        if silo_put > 0:
            parts.append(f"Stored {round(silo_put, 1)} wheat in the silo")
        parts.append(f"piled {round(total, 1)} units here — [E] to set a sell price on your own land")
        await self._send(player_id, {"type": "notice", "msg": " — ".join(parts)})

    # ---- set pile price -----------------------------------------------------

    async def _set_pile_price(self, player_id: int, resource_type: str, price):
        player = self.players.get(player_id)
        if not player:
            return
        key  = (player["x"], player["y"])
        pile = self.piles.get(key, {}).get(resource_type)
        if not pile or pile.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "No pile of that type here that you own."})
            return
        pk = self.parcel_at.get(key)
        par = self.world_parcels.get(pk) if pk else None
        if not par or par.get("owner_id") != player_id:
            await self._send(player_id, {
                "type": "notice",
                "msg": "Sell prices can only be set on piles that sit on your own land.",
            })
            return
        sp = None if price is None else max(0.0, float(price))
        pile_row = await queries.upsert_pile(
            pile.get("parcel_id"), player_id, *key, resource_type, pile["amount"], sp,
        )
        self.piles[key][resource_type] = dict(pile_row)
        await self._send(player_id, {"type": "notice",
            "msg": f"{resource_type}: {'not for sale' if sp is None else f'{sp}c/unit'}"})

    # ---- buy from pile ------------------------------------------------------

    async def _buy_pile(self, player_id: int, resource_type: str, amount: float):
        player = self.players.get(player_id)
        if not player:
            return
        key   = (player["x"], player["y"])
        pile  = self.piles.get(key, {}).get(resource_type)
        if not pile or pile.get("sell_price") is None:
            await self._send(player_id, {"type": "notice", "msg": "No priced pile here."})
            return
        if pile.get("owner_id") == player_id:
            await self._send(player_id, {"type": "notice", "msg": "That's your own pile."})
            return
        can = min(float(amount), pile["amount"], player["coins"] / pile["sell_price"])
        if can <= 0:
            await self._send(player_id, {"type": "notice",
                "msg": "No funds, or pile empty."})
            return
        can  = round(can, 2)
        cost = round(can * pile["sell_price"])

        # Town tax on player-to-player sale
        cost_after_tax, tax = self._apply_town_tax(cost, *key)
        if player["coins"] < cost:
            await self._send(player_id, {"type": "notice", "msg": f"Need {cost}c."})
            return

        player["coins"] -= cost
        pile["amount"] = round(pile["amount"] - can, 2)
        owner = self.players.get(pile["owner_id"])
        if owner:
            owner["coins"] += cost_after_tax

        if pile["amount"] <= 0:
            del self.piles[key][resource_type]
            await queries.delete_pile(*key, resource_type)
        else:
            await queries.upsert_pile(
                pile.get("parcel_id"), pile["owner_id"], *key,
                resource_type, pile["amount"], pile["sell_price"],
            )
        player.setdefault("_pending_pile_loads", []).append({
            "x": key[0], "y": key[1], "rtype": resource_type, "remaining": float(can),
        })
        tax_str = f" (+{tax}c town tax)" if tax else ""
        await self._send(player_id, {"type": "notice",
            "msg": f"Paid {cost}c for {can} {resource_type}. Stand on the pile to load into your barrow.{tax_str}"})

    # ---- NPC shops ----------------------------------------------------------

    async def _npc_shop_buy(self, player_id: int, shop: str, item: str):
        player = self.players.get(player_id)
        if not player or shop not in ("seed_shop", "general_store", "repair_shop"):
            return
        if not _near_shop(player, shop, self.towns):
            await self._send(player_id, {"type": "notice", "msg": "Move closer to the shop."})
            return
        if shop == "seed_shop":
            await self._seed_shop_buy(player_id, item)
        elif shop == "general_store":
            await self._general_store_buy(player_id, item)
        elif shop == "repair_shop":
            await self._repair(player_id, item)

    async def _seed_shop_buy(self, player_id: int, item: str):
        player  = self.players.get(player_id)
        catalog = SEED_SHOP_ITEMS.get(item)
        if not catalog:
            return
        if player["coins"] < catalog["cost"]:
            await self._send(player_id, {"type": "notice", "msg": f"Need {catalog['cost']}c."})
            return
        qty = catalog["qty"]
        if item == "fertilizer":
            space = effective_bucket_cap(player) - _bucket_total(player.get("bucket", {}))
            if space < qty:
                await self._send(player_id, {"type": "notice",
                    "msg": f"Need {qty} free barrow space for fertilizer (have {space})."})
                return
            player["coins"] -= catalog["cost"]
            b = player.setdefault("bucket", {})
            b["fertilizer"] = round(b.get("fertilizer", 0) + qty, 2)
        else:
            player["coins"] -= catalog["cost"]
            pocket = player.setdefault("pocket", {})
            pocket[item] = pocket.get(item, 0) + qty
        await self._send(player_id, {"type": "notice",
            "msg": f"Bought {catalog['label']} for {catalog['cost']}c."})

    async def _general_store_buy(self, player_id: int, item: str):
        player = self.players.get(player_id)
        if not item or "_" not in item:
            return
        component, _, level_s = item.partition("_")
        try:
            target = int(level_s)
        except ValueError:
            return
        level_key = f"wb_{component}_level"
        cost_map  = {"bucket": WB_BUCKET_COST, "tire": WB_TIRE_COST,
                     "handle": WB_HANDLE_COST,  "barrow": WB_BARROW_COST}.get(component)
        if not cost_map:
            return
        current = player.get(level_key, 1)
        if target != current + 1:
            await self._send(player_id, {"type": "notice", "msg": "Upgrade one level at a time."})
            return
        if target not in cost_map:
            await self._send(player_id, {"type": "notice", "msg": "Already at max level."})
            return
        cost = cost_map[target]
        if player["coins"] < cost:
            await self._send(player_id, {"type": "notice", "msg": f"Need {cost}c."})
            return
        player["coins"]  -= cost
        player[level_key] = target
        if component == "bucket":
            player["bucket_cap"] = WB_BUCKET_CAP.get(target, player["bucket_cap"])
        label = UPGRADE_COMPONENTS.get(component, (None,None,component))[2]
        await self._send(player_id, {"type": "notice",
            "msg": f"{label} upgraded to level {target}!"})

    async def _repair(self, player_id: int, component: str):
        player = self.players.get(player_id)
        if not player:
            return
        if not _near_shop(player, "repair_shop", self.towns):
            await self._send(player_id, {"type": "notice", "msg": "Move closer to the Repair Shop."})
            return
        if component == "flat":
            if not player.get("flat_tire"):
                await self._send(player_id, {"type": "notice", "msg": "Tyre isn't flat."})
                return
            if player["coins"] < REPAIR_FLAT_COST:
                await self._send(player_id, {"type": "notice", "msg": f"Need {REPAIR_FLAT_COST}c."})
                return
            player["coins"]    -= REPAIR_FLAT_COST
            player["flat_tire"] = 0
            await self._send(player_id, {"type": "notice", "msg": f"Flat fixed for {REPAIR_FLAT_COST}c."})
            return
        if component not in REPAIR_COST_PER_PCT:
            return
        cond_key = f"wb_{component}"
        current  = player.get(cond_key, 100.0)
        missing  = 100.0 - current
        if missing <= 0:
            await self._send(player_id, {"type": "notice", "msg": f"{component} is already 100%."})
            return
        cost = max(1, round(missing * REPAIR_COST_PER_PCT[component]))
        if player["coins"] < cost:
            can = player["coins"] / REPAIR_COST_PER_PCT[component]
            player[cond_key] = min(100.0, current + can)
            player["coins"]  = 0
            await self._send(player_id, {"type": "notice", "msg": f"Partial repair. {component}: {round(player[cond_key])}%"})
            return
        player["coins"] -= cost
        player[cond_key] = 100.0
        await self._send(player_id, {"type": "notice", "msg": f"{component} repaired for {cost}c."})

    async def _upgrade_wb(self, player_id: int, component: str):
        player = self.players.get(player_id)
        if not player:
            return
        if not _near_shop(player, "general_store", self.towns):
            await self._send(player_id, {"type": "notice", "msg": "Move closer to the General Store."})
            return
        current = player.get(f"wb_{component}_level", 1)
        await self._general_store_buy(player_id, f"{component}_{current + 1}")

    # ---- farming ------------------------------------------------------------

    async def _farm(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty  = player["x"], player["y"]
        parcel  = self._get_player_parcel(player)
        crop    = self.crops.get((tx, ty))
        now_utc = datetime.datetime.utcnow()

        # Frost-killed crop — till to clear stubble and prepare soil
        if crop and crop.get("winter_dead"):
            if not parcel or parcel.get("owner_id") != player_id:
                await self._send(player_id, {"type": "notice", "msg": "Not your land."})
                return
            if (tx, ty) in self.poor_soil:
                await self._send(player_id, {"type": "notice",
                    "msg": "Poor soil — deposit 1 dirt here ([I]) before you can till away the stubble."})
                return
            await queries.harvest_crop(crop["id"])
            del self.crops[(tx, ty)]
            await queries.upsert_soil_tile(tx, ty, 1)
            self.soil[(tx, ty)] = 1
            await self._send(player_id, {
                "type": "notice",
                "msg": "Tilled — frosted stubble cleared. Plant wheat in spring when the soil is tilled.",
            })
            return

        # Growing crop (alive)
        if crop and not crop.get("winter_dead"):
            ready_at = crop["ready_at"]
            if isinstance(ready_at, str):
                ready_at = datetime.datetime.fromisoformat(ready_at)
            if ready_at <= now_utc:
                if not parcel or parcel.get("owner_id") != player_id:
                    await self._send(player_id, {"type": "notice", "msg": "Not your land."})
                    return
                cdef = CROP_DEFS.get(crop["crop_type"], CROP_DEFS["wheat"])
                qty  = cdef["yield_fertilized"] if crop.get("fertilized_at") else cdef["yield_base"]
                space = effective_bucket_cap(player) - _bucket_total(player.get("bucket", {}))
                take  = min(qty, space)
                if take <= 0:
                    await self._send(player_id, {"type": "notice", "msg": "No space in bucket."})
                    return
                player.setdefault("bucket", {})[crop["crop_type"]] = round(
                    player["bucket"].get(crop["crop_type"], 0) + take, 2)
                del self.crops[(tx, ty)]
                await queries.harvest_crop(crop["id"])
                await queries.upsert_soil_tile(tx, ty, 0)
                self.soil[(tx, ty)] = 0
                await self._send(player_id, {"type": "notice", "msg": f"Harvested {round(take,1)} {crop['crop_type']}! Till before planting again."})
                return
            pocket = player.setdefault("pocket", {})
            bucket = player.setdefault("bucket", {})
            fert_b = float(bucket.get("fertilizer", 0) or 0)
            fert_p = float(pocket.get("fertilizer", 0) or 0)
            man_b  = float(bucket.get("manure", 0) or 0)
            if not crop.get("fertilized_at") and (fert_b >= 1 or fert_p > 0 or man_b >= 1):
                planted_at = crop["planted_at"]
                if isinstance(planted_at, str):
                    planted_at = datetime.datetime.fromisoformat(planted_at)
                elapsed = (now_utc - planted_at).total_seconds()
                cdef = CROP_DEFS.get(crop["crop_type"], CROP_DEFS["wheat"])
                if elapsed <= cdef["fertilize_window_s"]:
                    if fert_b >= 1:
                        bucket["fertilizer"] = round(fert_b - 1, 2)
                        if bucket["fertilizer"] <= 0:
                            del bucket["fertilizer"]
                        src = "fertilizer"
                    elif fert_p > 0:
                        pocket["fertilizer"] = fert_p - 1
                        if pocket["fertilizer"] <= 0:
                            del pocket["fertilizer"]
                        src = "fertilizer"
                    else:
                        bucket["manure"] = round(man_b - 1, 2)
                        if bucket["manure"] <= 0:
                            del bucket["manure"]
                        src = "manure"
                    new_ready = now_utc + datetime.timedelta(seconds=cdef["grow_time_fert_s"] - elapsed)
                    crop["fertilized_at"] = now_utc.isoformat()
                    crop["ready_at"]      = new_ready
                    await queries.fertilize_crop(crop["id"], new_ready)
                    note = "Fertilized! Crop grows faster." if src == "fertilizer" else "Applied manure — crop grows faster."
                    await self._send(player_id, {"type": "notice", "msg": note})
                    return
            mins = max(0, int((ready_at - now_utc).total_seconds() // 60))
            await self._send(player_id, {"type": "notice",
                "msg": f"Crop growing. ~{mins} min left."})
            return

        # No crop — own land only for till / plant
        if not parcel or parcel.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only farm on your own land."})
            return

        if self._soil_ready_for_planting(tx, ty):
            cdef = CROP_DEFS["wheat"]
            if self.season.season != cdef["plant_season"]:
                await self._send(player_id, {"type": "notice",
                    "msg": "You can only plant wheat in spring — wait for the next spring."})
                return
            pocket = player.setdefault("pocket", {})
            if pocket.get("wheat_seed", 0) <= 0:
                await self._send(player_id, {"type": "notice",
                    "msg": "Soil is tilled. You need wheat seeds (Seed Shop) to plant."})
                return
            for n in {**self.nodes, **self.structures}.values():
                if n["x"] == tx and n["y"] == ty:
                    await self._send(player_id, {"type": "notice", "msg": "Something else is here."})
                    return
            pocket["wheat_seed"] -= 1
            if pocket["wheat_seed"] <= 0:
                del pocket["wheat_seed"]
            ready_at = now_utc + datetime.timedelta(seconds=cdef["grow_time_s"])
            row      = await queries.create_crop(parcel["id"], player_id, tx, ty, "wheat", ready_at)
            row["ready_at"] = ready_at
            row["winter_dead"] = 0
            self.crops[(tx, ty)] = dict(row)
            await queries.upsert_soil_tile(tx, ty, 0)
            self.soil[(tx, ty)] = 0
            await self._send(player_id, {"type": "notice", "msg": "Planted wheat! Ready in ~20 min."})
            return

        if (tx, ty) in self.poor_soil:
            await self._send(player_id, {"type": "notice",
                "msg": "This soil is poor — press [I] with at least 1 dirt in your barrow to improve the tile, then till."})
            return

        await queries.upsert_soil_tile(tx, ty, 1)
        self.soil[(tx, ty)] = 1
        await self._send(player_id, {"type": "notice", "msg": "Tilled the soil. Plant wheat seeds in spring ([F])."})

    # ---- player market ------------------------------------------------------

    async def _market_config(self, player_id: int, prices: dict):
        player = self.players.get(player_id)
        if not player or not isinstance(prices, dict):
            return
        tx, ty = player["x"], player["y"]
        node   = next((n for n in self.structures.values()
                       if n.get("is_market") and n["x"] == tx and n["y"] == ty
                       and n["owner_id"] == player_id), None)
        if not node:
            await self._send(player_id, {"type": "notice", "msg": "Stand on your Player Market to configure it."})
            return
        node["config"]["prices"] = prices
        await queries.save_structure(node)
        await self._send(player_id, {"type": "notice", "msg": "Market prices updated."})

    async def _market_trade(self, player_id: int, action: str, resource_type: str, amount: float):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        node   = next((n for n in self.structures.values()
                       if n.get("is_market") and abs(n["x"]-tx)<=1 and abs(n["y"]-ty)<=1), None)
        if not node:
            await self._send(player_id, {"type": "notice", "msg": "No player market nearby."})
            return
        prices    = node.get("config", {}).get("prices", {})
        price     = prices.get(resource_type)
        if price is None:
            await self._send(player_id, {"type": "notice", "msg": f"Market doesn't trade {resource_type}."})
            return
        owner     = self.players.get(node["owner_id"])
        inventory = node.setdefault("inventory", {})

        if action == "sell":
            bucket = player.get("bucket", {})
            qty    = min(float(amount), bucket.get(resource_type, 0))
            if qty <= 0:
                await self._send(player_id, {"type": "notice", "msg": "Nothing to sell."})
                return
            earned = round(qty * price)
            if owner and owner["coins"] < earned:
                await self._send(player_id, {"type": "notice", "msg": "Market owner lacks funds."})
                return
            earned_after, tax = self._apply_town_tax(earned, tx, ty)
            bucket[resource_type] = round(bucket.get(resource_type, 0) - qty, 2)
            if bucket[resource_type] <= 0:
                del bucket[resource_type]
            player["coins"] += earned_after
            inventory[resource_type] = round(inventory.get(resource_type, 0) + qty, 2)
            if owner:
                owner["coins"] -= earned
            await self._send(player_id, {"type": "sold", "earned": earned_after, "coins": player["coins"]})
        elif action == "buy":
            inv_qty = inventory.get(resource_type, 0)
            space   = effective_bucket_cap(player) - _bucket_total(player.get("bucket", {}))
            qty     = min(float(amount), inv_qty, space, player["coins"] / price)
            if qty <= 0:
                await self._send(player_id, {"type": "notice", "msg": "Can't buy."})
                return
            qty  = round(qty, 2)
            cost = round(qty * price)
            cost_after, tax = self._apply_town_tax(cost, tx, ty)
            player["coins"] -= cost
            player.setdefault("bucket", {})[resource_type] = round(
                player["bucket"].get(resource_type, 0) + qty, 2)
            inventory[resource_type] = round(inv_qty - qty, 2)
            if owner:
                owner["coins"] += cost_after
            await self._send(player_id, {"type": "notice",
                "msg": f"Bought {qty} {resource_type} for {cost}c."})
        await queries.save_structure(node)

    # ---- town actions -------------------------------------------------------

    async def _town_action(self, player_id: int, msg: dict):
        player = self.players.get(player_id)
        if not player:
            return
        action = msg.get("action")
        town   = self._get_player_town(player)
        if not town:
            await self._send(player_id, {"type": "notice", "msg": "You're not in a town."})
            return
        is_leader  = player_id == town.get("leader_id")
        is_founder = player_id == town.get("founder_id")

        if action == "set_tax":
            if not is_leader:
                await self._send(player_id, {"type": "notice", "msg": "Only the town leader can set taxes."})
                return
            rate = float(msg.get("rate", 0))
            if not (0 <= rate <= MAX_TAX_RATE):
                await self._send(player_id, {"type": "notice", "msg": f"Tax rate must be 0–{int(MAX_TAX_RATE*100)}%."})
                return
            town["tax_rate"] = rate
            await queries.update_town(town)
            await self._broadcast_all({"type": "town_update", "town": self._town_wire(town)})
            await self._send(player_id, {"type": "notice",
                "msg": f"Town tax set to {int(rate*100)}%."})

        elif action == "rename":
            if not is_founder:
                await self._send(player_id, {"type": "notice", "msg": "Only the town founder can rename it."})
                return
            if town.get("custom_name"):
                await self._send(player_id, {"type": "notice", "msg": "Town already renamed (can only rename once)."})
                return
            name = str(msg.get("name", "")).strip()[:32]
            if not name:
                return
            town["custom_name"] = name
            await queries.update_town(town)
            await self._broadcast_all({"type": "town_update", "town": self._town_wire(town)})
            await self._send(player_id, {"type": "notice", "msg": f"Town renamed to {name}!"})

        elif action == "ban_structure":
            if not is_leader:
                await self._send(player_id, {"type": "notice", "msg": "Only the leader can ban structures."})
                return
            target = msg.get("target", "")
            bans   = self.town_bans.setdefault(town["id"], {"structures": set(), "goods": set()})
            if target in bans["structures"]:
                bans["structures"].discard(target)
                await queries.remove_ban(town["id"], "structure", target)
                await self._send(player_id, {"type": "notice", "msg": f"Ban on {target} lifted."})
            else:
                bans["structures"].add(target)
                await queries.set_ban(town["id"], "structure", target)
                await self._send(player_id, {"type": "notice", "msg": f"{target} banned in town."})

        elif action == "ban_good":
            if not is_leader:
                await self._send(player_id, {"type": "notice", "msg": "Only the leader can ban goods."})
                return
            target = msg.get("target", "")
            bans   = self.town_bans.setdefault(town["id"], {"structures": set(), "goods": set()})
            if target in bans["goods"]:
                bans["goods"].discard(target)
                await queries.remove_ban(town["id"], "good", target)
                await self._send(player_id, {"type": "notice", "msg": f"Ban on {target} lifted."})
            else:
                bans["goods"].add(target)
                await queries.set_ban(town["id"], "good", target)
                await self._send(player_id, {"type": "notice", "msg": f"{target} banned from sale in town."})

        elif action == "withdraw":
            if not is_leader:
                await self._send(player_id, {"type": "notice", "msg": "Only the leader can withdraw treasury."})
                return
            amount = min(int(msg.get("amount", 0)), town.get("treasury", 0))
            if amount <= 0:
                await self._send(player_id, {"type": "notice", "msg": "Nothing to withdraw."})
                return
            town["treasury"] -= amount
            player["coins"]  += amount
            await queries.update_town(town)
            await self._send(player_id, {"type": "notice", "msg": f"Withdrew {amount}c from treasury."})

    # ---- voting -------------------------------------------------------------

    async def _vote(self, player_id: int, candidate_id: int):
        player = self.players.get(player_id)
        if not player or not candidate_id:
            return
        town = self._get_player_town(player)
        if not town or not town.get("hall_built"):
            await self._send(player_id, {"type": "notice", "msg": "No Town Hall here."})
            return
        # Must be at Town Hall
        hall = next((n for n in self.structures.values()
                     if n.get("is_town_hall") and abs(n["x"]-player["x"])<=2
                     and abs(n["y"]-player["y"])<=2 and self._get_player_town(player)), None)
        if not hall:
            await self._send(player_id, {"type": "notice", "msg": "Stand near the Town Hall to vote."})
            return
        # Check voting window
        next_el = town.get("next_election_at")
        if isinstance(next_el, str):
            next_el = datetime.datetime.fromisoformat(next_el)
        if not next_el:
            await self._send(player_id, {"type": "notice", "msg": "No election scheduled."})
            return
        now = datetime.datetime.utcnow()
        window_start = next_el - datetime.timedelta(hours=VOTING_WINDOW_HOURS)
        if not (window_start <= now <= next_el):
            remaining = int((window_start - now).total_seconds() // 3600)
            await self._send(player_id, {"type": "notice",
                "msg": f"Voting opens in ~{remaining}h."})
            return
        # Must be a landowner in this town
        owners = await queries.get_town_landowners(town["id"])
        if not any(o["id"] == player_id for o in owners):
            await self._send(player_id, {"type": "notice", "msg": "Only town landowners can vote."})
            return
        cycle = town.get("vote_cycle", 1)
        await queries.cast_vote(town["id"], player_id, candidate_id, cycle)
        candidate = self.players.get(candidate_id)
        name = candidate["username"] if candidate else f"#{candidate_id}"
        await self._send(player_id, {"type": "notice", "msg": f"Voted for {name}."})

    # ------------------------------------------------------------------- tick

    async def tick(self, resource_tick_s: int, persist_interval_s: int):
        now = time.monotonic()

        prev_season = self.season.season
        if self.season.tick():
            new_season = self.season.season
            await queries.save_season_state(new_season)
            if new_season == 3:
                await self._kill_unharvested_crops_for_winter()
                await self._winter_rot_piles()
            if prev_season == 3 and new_season == 0:
                await self._grow_roads_new_year()
            await self._broadcast_all({"type": "season_change", "season": self.season.wire()})

        if now - self._last_resource_tick >= resource_tick_s:
            elapsed = now - self._last_resource_tick
            self._last_resource_tick = now
            await self._do_resource_tick(elapsed)

        if now - self._last_market_drift >= MARKET_DRIFT_INTERVAL:
            self._last_market_drift = now
            await self._do_market_drift()

        # Election check once per minute
        if now - self._last_election_check >= 60:
            self._last_election_check = now
            await self._do_election_check()

        await self._broadcast_state()

        if now - self._last_persist >= persist_interval_s:
            self._last_persist = now
            for p in self.players.values():
                if p["id"] in self.sockets:
                    await queries.save_player(p)
            for n in self.nodes.values():
                await queries.save_node(n)
            for s in self.structures.values():
                await queries.save_structure(s)
            for t in self.towns.values():
                await queries.update_town(t)

    async def _do_resource_tick(self, elapsed: float):
        all_nodes = {**self.nodes, **self.structures}
        for node in all_nodes.values():
            if node.get("construction_active"):
                continue
            if node.get("is_market") or node.get("is_town_hall"):
                continue
            node["current_amount"] = min(
                node["max_amount"],
                node["current_amount"] + node["replenish_rate"] * elapsed,
            )
        for player in self.players.values():
            if player["id"] not in self.sockets:
                continue
            px, py = player["x"], player["y"]
            cap   = effective_bucket_cap(player)
            load  = _bucket_total(player.get("bucket", {}))
            space = cap - load

            # Paid pile purchases: load into barrow over time while standing on the tile
            pending = player.get("_pending_pile_loads") or []
            new_pending: list[dict] = []
            for pl in pending:
                rem = float(pl.get("remaining", 0))
                if rem <= 0:
                    continue
                if player["x"] != pl["x"] or player["y"] != pl["y"]:
                    new_pending.append(pl)
                    continue
                load = _bucket_total(player.get("bucket", {}))
                space = cap - load
                if space <= 0:
                    new_pending.append(pl)
                    continue
                rtype = pl["rtype"]
                rate = COLLECTION_RATES.get(rtype, COLLECTION_RATE) * PILE_COLLECTION_MULT
                take = min(rate, space, rem)
                take = round(take, 2)
                if take <= 0:
                    new_pending.append(pl)
                    continue
                player.setdefault("bucket", {})[rtype] = round(
                    player["bucket"].get(rtype, 0) + take, 2)
                rem = round(rem - take, 2)
                if rem > 0:
                    pl["remaining"] = rem
                    new_pending.append(pl)
            player["_pending_pile_loads"] = new_pending

            load = _bucket_total(player.get("bucket", {}))
            space = cap - load
            pile_map = self.piles.get((px, py))
            if pile_map and space > 0:
                for rtype, pile in list(pile_map.items()):
                    if not self._player_can_free_pick_pile(player, pile):
                        continue
                    if pile["amount"] <= 0:
                        continue
                    rate = COLLECTION_RATES.get(rtype, COLLECTION_RATE) * PILE_COLLECTION_MULT
                    load = _bucket_total(player.get("bucket", {}))
                    space = cap - load
                    if space <= 0:
                        break
                    take = min(rate, space, pile["amount"])
                    take = round(take, 2)
                    if take <= 0:
                        continue
                    pile["amount"] = round(pile["amount"] - take, 2)
                    player.setdefault("bucket", {})[rtype] = round(
                        player["bucket"].get(rtype, 0) + take, 2)
                    if pile["amount"] <= 0:
                        del self.piles[(px, py)][rtype]
                        await queries.delete_pile(px, py, rtype)
                    else:
                        await queries.upsert_pile(
                            pile.get("parcel_id"), pile["owner_id"], px, py, rtype,
                            pile["amount"], pile.get("sell_price"),
                        )

            load = _bucket_total(player.get("bucket", {}))
            space = cap - load
            for node in all_nodes.values():
                if node.get("construction_active"):
                    continue
                if node.get("is_market") or node.get("is_town_hall"):
                    continue
                if abs(px - node["x"]) > COLLECTION_RADIUS:
                    continue
                if abs(py - node["y"]) > COLLECTION_RADIUS:
                    continue
                cap   = effective_bucket_cap(player)
                load  = _bucket_total(player.get("bucket", {}))
                space = cap - load
                if space <= 0 or node["current_amount"] <= 0:
                    continue
                rtype = node["node_type"]
                rate  = COLLECTION_RATES.get(rtype, COLLECTION_RATE)
                collected = min(rate, space, node["current_amount"])
                node["current_amount"] = max(0.0, node["current_amount"] - collected)
                player.setdefault("bucket", {})[rtype] = round(
                    player["bucket"].get(rtype, 0) + collected, 2)
                if node.get("is_structure"):
                    owner = self.players.get(node["owner_id"])
                    if owner and node["owner_id"] != player["id"]:
                        owner["coins"] += node.get("collect_fee", 1)

    async def _do_market_drift(self):
        for rtype, base in MARKET_BASE_PRICES.items():
            sold    = self.sales_volume.get(rtype, 0.0)
            current = self.prices.get(rtype, base)
            if sold >= MARKET_DRIFT_INTERVAL:
                new_price = max(round(base * 0.5, 2), round(current * 0.85, 2))
            else:
                new_price = min(round(base * 2.0, 2), round(current * 1.10, 2))
            self.prices[rtype]       = new_price
            self.sales_volume[rtype] = 0.0
        await queries.update_market_prices(self.prices)

    async def _do_election_check(self):
        """Resolve any towns whose election window has just closed."""
        now = datetime.datetime.utcnow()
        for town in self.towns.values():
            next_el = town.get("next_election_at")
            if not next_el or not town.get("hall_built"):
                continue
            if isinstance(next_el, str):
                next_el = datetime.datetime.fromisoformat(next_el)
            if now >= next_el:
                cycle   = town.get("vote_cycle", 1)
                results = await queries.get_vote_results(town["id"], cycle)
                if results:
                    winner_id = results[0]["candidate_id"]
                    town["leader_id"] = winner_id
                    winner = self.players.get(winner_id)
                    wname  = winner["username"] if winner else f"#{winner_id}"
                    await self._broadcast_all({"type": "notice",
                        "msg": f"Election in {town.get('custom_name') or town['name']}: {wname} elected leader!"})
                town["vote_cycle"]      = cycle + 1
                town["next_election_at"] = now + datetime.timedelta(days=ELECTION_CYCLE_DAYS)
                await queries.update_town(town)
                await self._broadcast_all({"type": "town_update", "town": self._town_wire(town)})

    def _connected_players_wire(self) -> list[dict]:
        """Other clients only need wheelbarrows for players with an active WebSocket."""
        return [
            {"id": p["id"], "username": p["username"], "x": p["x"], "y": p["y"],
             "flat_tire": p.get("flat_tire", 0)}
            for p in self.players.values() if p["id"] in self.sockets
        ]

    async def _broadcast_state(self):
        if not self.sockets:
            return
        all_players = self._connected_players_wire()
        all_structs  = [self._node_wire(n) for n in self.structures.values()]

        for pid, ws in list(self.sockets.items()):
            player = self.players.get(pid)
            if not player:
                continue
            px, py = player["x"], player["y"]
            # Viewport-culled nodes / piles / crops
            nearby_nodes = [
                self._node_wire(n) for n in self.nodes.values()
                if abs(n["x"] - px) <= VIEWPORT_RADIUS and abs(n["y"] - py) <= VIEWPORT_RADIUS
            ]
            nearby_piles = [
                self._pile_wire(pile, rtype)
                for (tile_key), pile_map in self.piles.items()
                for rtype, pile in pile_map.items()
                if abs(tile_key[0] - px) <= VIEWPORT_RADIUS and abs(tile_key[1] - py) <= VIEWPORT_RADIUS
            ]
            nearby_crops = [
                self._crop_wire(c) for c in self.crops.values()
                if abs(c["x"] - px) <= VIEWPORT_RADIUS and abs(c["y"] - py) <= VIEWPORT_RADIUS
            ]
            nearby_roads = [
                {"x": rx, "y": ry}
                for (rx, ry) in self.road_tiles
                if abs(rx - px) <= VIEWPORT_RADIUS and abs(ry - py) <= VIEWPORT_RADIUS
            ]
            nearby_soil = self._nearby_soil_tiles(px, py)
            nearby_water = self._nearby_water_tiles(px, py)
            nearby_bridges = self._nearby_bridge_tiles(px, py)
            nearby_poor = self._nearby_poor_soil_tiles(px, py, pid)
            try:
                await ws.send_json({
                    "type":       "tick",
                    "players":    all_players,
                    "player":     self._player_wire(player),
                    "nodes":      nearby_nodes + all_structs,
                    "piles":      nearby_piles,
                    "crops":      nearby_crops,
                    "roads":      nearby_roads,
                    "soil_tiles": nearby_soil,
                    "water_tiles": nearby_water,
                    "bridge_tiles": nearby_bridges,
                    "poor_soil_tiles": nearby_poor,
                    "prices":     self.prices,
                    "season":     self.season.wire(),
                })
            except Exception:
                pass

    async def _broadcast_all(self, msg: dict):
        for ws in list(self.sockets.values()):
            try:
                await ws.send_json(msg)
            except Exception:
                pass

    async def _send(self, player_id: int, msg: dict):
        ws = self.sockets.get(player_id)
        if ws:
            try:
                await ws.send_json(msg)
            except Exception:
                pass

    # ----------------------------------------------------------------- wires

    def _player_wire(self, p: dict) -> dict:
        eff = effective_bucket_cap(p)
        return {
            "id": p["id"], "x": p["x"], "y": p["y"],
            "coins": p["coins"], "bucket": p.get("bucket", {}),
            "bucket_cap": p["bucket_cap"],
            "bucket_cap_effective": eff,
            "pocket": p.get("pocket", {}),
            "wb_paint":  round(p.get("wb_paint",  100), 1),
            "wb_tire":   round(p.get("wb_tire",   100), 1),
            "wb_handle": round(p.get("wb_handle", 100), 1),
            "wb_barrow": round(p.get("wb_barrow", 100), 1),
            "flat_tire": p.get("flat_tire", 0),
            "wb_bucket_level": p.get("wb_bucket_level", 1),
            "wb_tire_level":   p.get("wb_tire_level",   1),
            "wb_handle_level": p.get("wb_handle_level", 1),
            "wb_barrow_level": p.get("wb_barrow_level", 1),
        }

    def _node_wire(self, n: dict) -> dict:
        st = n.get("structure_type")
        out = {
            "id": n["id"], "x": n["x"], "y": n["y"],
            "type":         n["node_type"],
            "amount":       round(n["current_amount"], 1),
            "max":          n["max_amount"],
            "is_structure": n.get("is_structure", False),
            "is_market":    n.get("is_market", False),
            "is_town_hall": n.get("is_town_hall", False),
            "is_silo":      bool(n.get("is_silo")),
            "owner_name":   n.get("owner_name"),
            "owner_id":     n.get("owner_id"),
        }
        if st:
            out["structure_type"] = st
        out["construction_active"] = bool(n.get("construction_active"))
        if n.get("construction_active"):
            cons = (n.get("config") or {}).get("construction") or {}
            fr = foundation_remaining(cons)
            br = building_remaining(cons)
            out["construction"] = {
                "foundation_remaining": {k: round(v, 1) for k, v in fr.items() if v > 0},
                "building_remaining": {k: round(v, 1) for k, v in br.items() if v > 0},
                "foundation_done": bool(cons.get("foundation_done")),
            }
        if n.get("is_silo"):
            inv = n.get("inventory") or {}
            cap = float(STRUCTURE_DEFS.get(st or "", {}).get("silo_capacity", 0) or 0)
            out["silo_wheat"] = round(float(inv.get("wheat", 0) or 0), 1)
            out["silo_capacity"] = cap
        if n.get("node_type") == "wood" and not n.get("is_structure"):
            out["tree_variant"] = int(n.get("tree_variant") or 0)
        return out

    def _parcel_wire(self, p: dict) -> dict:
        return {
            "id": p["id"], "x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"],
            "price":      p.get("price"),
            "town_id":    p.get("town_id"),
            "owner_id":   p.get("owner_id"),
            "owner_name": p.get("owner_name"),
        }

    def _town_wire(self, t: dict) -> dict:
        return {
            "id": t["id"],
            "name":        t.get("custom_name") or t["name"],
            "raw_name":    t["name"],
            "center_x":    t["center_x"],
            "center_y":    t["center_y"],
            "boundary":    t["boundary"],
            "tax_rate":    t.get("tax_rate", 0),
            "treasury":    t.get("treasury", 0),
            "hall_built":  bool(t.get("hall_built")),
            "leader_id":   t.get("leader_id"),
            "founder_id":  t.get("founder_id"),
        }

    def _pile_wire(self, pile: dict, rtype: str) -> dict:
        return {
            "x": pile["x"], "y": pile["y"],
            "resource_type": rtype,
            "amount":        round(pile["amount"], 1),
            "sell_price":    pile.get("sell_price"),
            "owner_id":      pile.get("owner_id"),
        }

    def _crop_wire(self, c: dict) -> dict:
        now      = datetime.datetime.utcnow()
        ready_at = c["ready_at"]
        if isinstance(ready_at, str):
            ready_at = datetime.datetime.fromisoformat(ready_at)
        wd = bool(c.get("winter_dead"))
        return {
            "x": c["x"], "y": c["y"],
            "crop_type":   c["crop_type"],
            "owner_id":    c["owner_id"],
            "ready":       (not wd) and (ready_at <= now),
            "fertilized":  (not wd) and (c.get("fertilized_at") is not None),
            "winter_dead": wd,
        }

    def _all_npc_markets_wire(self) -> list[dict]:
        out: list[dict] = []
        for t in self.towns.values():
            d = t.get("npc_district") or {}
            m = d.get("market")
            if m and len(m) >= 2:
                out.append({"x": int(m[0]), "y": int(m[1])})
        if not out:
            out.append({"x": MARKET_TILE[0], "y": MARKET_TILE[1]})
        return out

    def _all_npc_shops_wire(self) -> list[dict]:
        out: list[dict] = []
        for t in self.towns.values():
            d = t.get("npc_district") or {}
            for k in ("seed_shop", "general_store", "repair_shop"):
                pos = d.get(k)
                if pos and len(pos) >= 2:
                    out.append({"key": k, "x": int(pos[0]), "y": int(pos[1]), "label": NPC_SHOP_LABELS[k]})
        if not out:
            for k, v in NPC_SHOP_LOCATIONS.items():
                out.append({"key": k, "x": v[0], "y": v[1], "label": NPC_SHOP_LABELS[k]})
        return out

    def _nearby_soil_tiles(self, px: int, py: int) -> list[dict]:
        out: list[dict] = []
        for (sx, sy), tv in self.soil.items():
            if abs(sx - px) <= VIEWPORT_RADIUS and abs(sy - py) <= VIEWPORT_RADIUS:
                out.append({"x": sx, "y": sy, "tilled": int(tv)})
        return out

    def _nearby_water_tiles(self, px: int, py: int) -> list[dict]:
        return [
            {"x": x, "y": y}
            for (x, y) in self.water_tiles
            if abs(x - px) <= VIEWPORT_RADIUS and abs(y - py) <= VIEWPORT_RADIUS
        ]

    def _nearby_bridge_tiles(self, px: int, py: int) -> list[dict]:
        return [
            {"x": x, "y": y}
            for (x, y) in self.bridge_tiles
            if abs(x - px) <= VIEWPORT_RADIUS and abs(y - py) <= VIEWPORT_RADIUS
        ]

    def _nearby_poor_soil_tiles(self, px: int, py: int, player_id: int) -> list[dict]:
        """Only tiles on land this player owns — used for [I] hints; not shown to others."""
        out: list[dict] = []
        for (x, y) in self.poor_soil:
            if abs(x - px) > VIEWPORT_RADIUS or abs(y - py) > VIEWPORT_RADIUS:
                continue
            pid = self.parcel_at.get((x, y))
            if pid is None:
                continue
            par = self.world_parcels.get(pid)
            if par and par.get("owner_id") == player_id:
                out.append({"x": x, "y": y})
        return out

    def full_state(self, player_id: int) -> dict:
        player = self.players[player_id]
        px, py = player["x"], player["y"]
        nearby_nodes = [
            self._node_wire(n) for n in self.nodes.values()
            if abs(n["x"]-px) <= VIEWPORT_RADIUS and abs(n["y"]-py) <= VIEWPORT_RADIUS
        ]
        nearby_piles = [
            self._pile_wire(pile, rtype)
            for tile_key, pile_map in self.piles.items()
            for rtype, pile in pile_map.items()
            if abs(tile_key[0]-px) <= VIEWPORT_RADIUS and abs(tile_key[1]-py) <= VIEWPORT_RADIUS
        ]
        nearby_roads = [
            {"x": rx, "y": ry}
            for (rx, ry) in self.road_tiles
            if abs(rx - px) <= VIEWPORT_RADIUS and abs(ry - py) <= VIEWPORT_RADIUS
        ]
        nearby_soil = self._nearby_soil_tiles(px, py)
        nearby_water = self._nearby_water_tiles(px, py)
        nearby_bridges = self._nearby_bridge_tiles(px, py)
        nearby_poor = self._nearby_poor_soil_tiles(px, py, player_id)
        return {
            "type":    "init",
            "player":  self._player_wire(player),
            "players": self._connected_players_wire(),
            "nodes":   nearby_nodes + [self._node_wire(n) for n in self.structures.values()],
            "parcels": [self._parcel_wire(p) for p in self.world_parcels.values()],
            "piles":   nearby_piles,
            "roads":   nearby_roads,
            "soil_tiles": nearby_soil,
            "water_tiles": nearby_water,
            "bridge_tiles": nearby_bridges,
            "poor_soil_tiles": nearby_poor,
            "crops":       [self._crop_wire(c) for c in self.crops.values()],
            "npc_markets": self._all_npc_markets_wire(),
            "npc_shops":   self._all_npc_shops_wire(),
            "towns":       [self._town_wire(t) for t in self.towns.values()],
            "prices":  self.prices,
            "season":  self.season.wire(),
            "world":   {"w": WORLD_W, "h": WORLD_H},
        }


engine = GameEngine()
