"""
In-memory game state. All mutation happens here; the DB handles persistence.

v0.5.0: worlds are 1000×1000; parcels are variable-size from world_parcels;
towns have polygon boundaries; transactions carry town taxes.
"""
import asyncio
import datetime
import math
import time
import uuid
from typing import Optional

from fastapi import WebSocket

from server.game.constants import (
    WORLD_W, WORLD_H, COLLECTION_RADIUS, COLLECTION_RATE,
    MARKET_TILE, STRUCTURE_DEFS, MARKET_BASE_PRICES,
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
from server.game.wb_condition import apply_move_decay, is_immobile
from server.db import queries


def _bucket_total(bucket: dict) -> float:
    return sum(bucket.values())

def _near_shop(player: dict, shop_key: str) -> bool:
    sx, sy = NPC_SHOP_LOCATIONS[shop_key]
    return (abs(player["x"] - sx) <= NPC_SHOP_ADJACENCY and
            abs(player["y"] - sy) <= NPC_SHOP_ADJACENCY)

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
        self.prices: dict[str, float] = {}
        self.sales_volume: dict[str, float] = {r: 0.0 for r in MARKET_BASE_PRICES}
        self.season = SeasonClock()

        self._last_resource_tick = time.monotonic()
        self._last_persist       = time.monotonic()
        self._last_market_drift  = time.monotonic()
        self._last_election_check = time.monotonic()

    # ------------------------------------------------------------------ load

    async def load(self):
        # World generation first (no-op if already done)
        from server.game.world_gen import generate_world_if_needed
        await generate_world_if_needed()

        # Load towns
        for t in await queries.load_all_towns():
            self.towns[t["id"]] = dict(t)

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
        for crop in await queries.load_all_crops():
            self.crops[(crop["x"], crop["y"])] = dict(crop)
        self.prices = await queries.get_market_prices()
        self.town_bans = await queries.load_town_bans()

        season_row = await queries.load_season_state()
        if season_row:
            self.season.load_from_db(season_row["season"], season_row["season_start"])

    def _struct_to_node(self, struct: dict) -> dict:
        sdef = STRUCTURE_DEFS.get(struct["structure_type"], {})
        return {
            "id":             struct["id"],
            "x":              struct["x"],
            "y":              struct["y"],
            "node_type":      sdef.get("produces") or struct["structure_type"],
            "structure_type": struct["structure_type"],
            "current_amount": 0.0,
            "max_amount":     sdef.get("max_amount", 0),
            "replenish_rate": sdef.get("replenish_rate", 0),
            "collect_fee":    sdef.get("collect_fee", 0),
            "owner_id":       struct["owner_id"],
            "owner_name":     struct["owner_name"],
            "is_structure":   True,
            "is_market":      sdef.get("is_market", False),
            "is_town_hall":   sdef.get("is_town_hall", False),
            "inventory":      struct.get("inventory", {}),
            "config":         struct.get("config", {}),
        }

    # ---------------------------------------------------------------- helpers

    def _get_player_parcel(self, player: dict) -> Optional[dict]:
        pid = self.parcel_at.get((player["x"], player["y"]))
        return self.world_parcels.get(pid) if pid else None

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
        player.setdefault("wb_paint",        100.0)
        player.setdefault("wb_tire",         100.0)
        player.setdefault("wb_handle",       100.0)
        player.setdefault("flat_tire",       0)
        player.setdefault("wb_bucket_level", 1)
        player.setdefault("wb_tire_level",   1)
        player.setdefault("wb_handle_level", 1)
        player.setdefault("wb_barrow_level", 1)
        player["bucket_cap"] = WB_BUCKET_CAP.get(player["wb_bucket_level"], 10)
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

    # ---- movement -----------------------------------------------------------

    def _move(self, player_id: int, direction: str):
        player = self.players.get(player_id)
        if not player:
            return
        if is_immobile(player):
            asyncio.ensure_future(self._send(player_id, {
                "type": "notice", "msg": "Handle broken — go to Repair Shop.",
            }))
            return
        dx, dy = {"up": (0,-1), "down": (0,1), "left": (-1,0), "right": (1,0)}.get(direction, (0,0))
        if dx == 0 and dy == 0:
            return
        nx, ny = player["x"] + dx, player["y"] + dy
        if not (0 <= nx < WORLD_W and 0 <= ny < WORLD_H):
            return
        player["x"], player["y"] = nx, ny
        events = apply_move_decay(player)
        for ev in events:
            if ev == "flat_tire":
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": "Flat tyre! Movement is slower. Find the Repair Shop."}))
            elif ev == "handle_break":
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": "Handle snapped! You can't move. Find the Repair Shop."}))
            elif ev.startswith("spill:"):
                _, rtype, amt = ev.split(":")
                asyncio.ensure_future(self._send(player_id, {"type": "notice",
                    "msg": f"Hole in barrow — spilled {amt} {rtype}!"}))

    # ---- NPC market ---------------------------------------------------------

    async def _sell_npc_market(self, player_id: int):
        player = self.players.get(player_id)
        if not player or (player["x"], player["y"]) != MARKET_TILE:
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

        # Town bans check
        town = self._get_player_town(player)
        if town:
            bans = self.town_bans.get(town["id"], {})
            if structure_type in bans.get("structures", set()):
                await self._send(player_id, {"type": "notice",
                    "msg": f"Building {structure_type} is banned in {town.get('custom_name') or town['name']}."})
                return

        tx, ty = player["x"], player["y"]
        for n in {**self.nodes, **self.structures}.values():
            if n["x"] == tx and n["y"] == ty:
                await self._send(player_id, {"type": "notice", "msg": "Something is already here."})
                return

        sdef = STRUCTURE_DEFS[structure_type]
        if player["coins"] < sdef["cost_coins"]:
            await self._send(player_id, {"type": "notice", "msg": f"Need {sdef['cost_coins']}c."})
            return
        for rtype, amt in sdef["cost_resources"].items():
            if player.get("bucket", {}).get(rtype, 0) < amt:
                await self._send(player_id, {"type": "notice", "msg": f"Need {amt} {rtype} in bucket."})
                return

        # Special: town hall — only one per town zone
        if sdef.get("is_town_hall"):
            if town:
                if town.get("hall_built"):
                    await self._send(player_id, {"type": "notice",
                        "msg": f"{town.get('custom_name') or town['name']} already has a Town Hall."})
                    return

        player["coins"] -= sdef["cost_coins"]
        for rtype, amt in sdef["cost_resources"].items():
            player["bucket"][rtype] = round(player["bucket"].get(rtype, 0) - amt, 2)
            if player["bucket"][rtype] <= 0:
                del player["bucket"][rtype]

        struct_row = await queries.create_structure(parcel["id"], tx, ty, structure_type)
        node = self._struct_to_node(struct_row)
        self.structures[node["id"]] = node

        # Town hall: claim town
        if sdef.get("is_town_hall") and town:
            town["hall_built"]   = 1
            town["founder_id"]   = player_id
            town["leader_id"]    = player_id
            import datetime
            town["next_election_at"] = datetime.datetime.utcnow() + datetime.timedelta(days=ELECTION_CYCLE_DAYS)
            await queries.update_town(town)
            await self._send(player_id, {"type": "notice",
                "msg": f"You founded {town.get('custom_name') or town['name']}! You can now set taxes and rename it."})
            await self._broadcast_all({"type": "town_update", "town": self._town_wire(town)})

        await self._send(player_id, {
            "type":      "built",
            "structure": self._node_wire(node),
            "coins":     player["coins"],
        })

    # ---- unload to pile -----------------------------------------------------

    async def _unload(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        parcel = self._get_player_parcel(player)
        if not parcel or parcel.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only pile resources on your own land."})
            return
        bucket = player.get("bucket", {})
        if not bucket:
            await self._send(player_id, {"type": "notice", "msg": "Bucket is empty."})
            return
        tx, ty = player["x"], player["y"]
        key = (tx, ty)
        self.piles.setdefault(key, {})
        total = 0.0
        for rtype, amt in list(bucket.items()):
            if amt <= 0:
                continue
            existing  = self.piles[key].get(rtype, {})
            new_amt   = round(existing.get("amount", 0) + amt, 2)
            pile_row  = await queries.upsert_pile(parcel["id"], player_id, tx, ty, rtype, new_amt, existing.get("sell_price"))
            self.piles[key][rtype] = dict(pile_row)
            total += amt
        player["bucket"] = {}
        await self._send(player_id, {"type": "notice", "msg": f"Piled {round(total,1)} units. Press [E] to set a price."})

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
        sp = None if price is None else max(0.0, float(price))
        pile_row = await queries.upsert_pile(pile["parcel_id"], player_id, *key, resource_type, pile["amount"], sp)
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
        bucket = player.setdefault("bucket", {})
        space  = player["bucket_cap"] - _bucket_total(bucket)
        can    = min(float(amount), space, pile["amount"],
                     player["coins"] / pile["sell_price"])
        if can <= 0:
            await self._send(player_id, {"type": "notice",
                "msg": "No space, no funds, or pile empty."})
            return
        can  = round(can, 2)
        cost = round(can * pile["sell_price"])

        # Town tax on player-to-player sale
        cost_after_tax, tax = self._apply_town_tax(cost, *key)
        if player["coins"] < cost:
            await self._send(player_id, {"type": "notice", "msg": f"Need {cost}c."})
            return

        player["coins"]   -= cost
        bucket[resource_type] = round(bucket.get(resource_type, 0) + can, 2)
        pile["amount"]    = round(pile["amount"] - can, 2)
        owner = self.players.get(pile["owner_id"])
        if owner:
            owner["coins"] += cost_after_tax

        if pile["amount"] <= 0:
            del self.piles[key][resource_type]
            await queries.delete_pile(*key, resource_type)
        else:
            await queries.upsert_pile(pile["parcel_id"], pile["owner_id"], *key,
                                      resource_type, pile["amount"], pile["sell_price"])
        tax_str = f" (+{tax}c town tax)" if tax else ""
        await self._send(player_id, {"type": "notice",
            "msg": f"Bought {can} {resource_type} for {cost}c{tax_str}."})

    # ---- NPC shops ----------------------------------------------------------

    async def _npc_shop_buy(self, player_id: int, shop: str, item: str):
        player = self.players.get(player_id)
        if not player or shop not in NPC_SHOP_LOCATIONS:
            return
        if not _near_shop(player, shop):
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
        player["coins"] -= catalog["cost"]
        pocket = player.setdefault("pocket", {})
        pocket[item] = pocket.get(item, 0) + catalog["qty"]
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
        if not _near_shop(player, "repair_shop"):
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
        if not _near_shop(player, "general_store"):
            await self._send(player_id, {"type": "notice", "msg": "Move closer to the General Store."})
            return
        current = player.get(f"wb_{component}_level", 1)
        await self._general_store_buy(player_id, f"{component}_{current + 1}")

    # ---- farming ------------------------------------------------------------

    async def _farm(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty   = player["x"], player["y"]
        parcel   = self._get_player_parcel(player)
        crop     = self.crops.get((tx, ty))
        now_utc  = datetime.datetime.utcnow()

        if crop and not crop.get("harvested"):
            ready_at = crop["ready_at"]
            if isinstance(ready_at, str):
                ready_at = datetime.datetime.fromisoformat(ready_at)
            if ready_at <= now_utc:
                if not parcel or parcel.get("owner_id") != player_id:
                    await self._send(player_id, {"type": "notice", "msg": "Not your land."})
                    return
                cdef = CROP_DEFS.get(crop["crop_type"], CROP_DEFS["wheat"])
                qty  = cdef["yield_fertilized"] if crop.get("fertilized_at") else cdef["yield_base"]
                space = player["bucket_cap"] - _bucket_total(player.get("bucket", {}))
                take  = min(qty, space)
                if take <= 0:
                    await self._send(player_id, {"type": "notice", "msg": "No space in bucket."})
                    return
                player.setdefault("bucket", {})[crop["crop_type"]] = round(
                    player["bucket"].get(crop["crop_type"], 0) + take, 2)
                crop["harvested"] = 1
                del self.crops[(tx, ty)]
                await queries.harvest_crop(crop["id"])
                await self._send(player_id, {"type": "notice", "msg": f"Harvested {round(take,1)} {crop['crop_type']}!"})
                return
            # Try fertilize
            pocket = player.get("pocket", {})
            if not crop.get("fertilized_at") and pocket.get("fertilizer", 0) > 0:
                planted_at = crop["planted_at"]
                if isinstance(planted_at, str):
                    planted_at = datetime.datetime.fromisoformat(planted_at)
                elapsed = (now_utc - planted_at).total_seconds()
                cdef = CROP_DEFS.get(crop["crop_type"], CROP_DEFS["wheat"])
                if elapsed <= cdef["fertilize_window_s"]:
                    pocket["fertilizer"] -= 1
                    if pocket["fertilizer"] <= 0:
                        del pocket["fertilizer"]
                    new_ready = now_utc + datetime.timedelta(seconds=cdef["grow_time_fert_s"] - elapsed)
                    crop["fertilized_at"] = now_utc.isoformat()
                    crop["ready_at"]      = new_ready
                    await queries.fertilize_crop(crop["id"], new_ready)
                    await self._send(player_id, {"type": "notice", "msg": "Fertilized! Crop grows faster."})
                    return
            mins = max(0, int((ready_at - now_utc).total_seconds() // 60))
            await self._send(player_id, {"type": "notice",
                "msg": f"Crop growing. ~{mins} min left."})
            return

        # Plant
        if not parcel or parcel.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only farm on your own land."})
            return
        pocket = player.setdefault("pocket", {})
        if pocket.get("wheat_seed", 0) <= 0:
            await self._send(player_id, {"type": "notice",
                "msg": "No wheat seeds. Buy from Seed Shop."})
            return
        for n in {**self.nodes, **self.structures}.values():
            if n["x"] == tx and n["y"] == ty:
                await self._send(player_id, {"type": "notice", "msg": "Something else is here."})
                return
        pocket["wheat_seed"] -= 1
        if pocket["wheat_seed"] <= 0:
            del pocket["wheat_seed"]
        cdef     = CROP_DEFS["wheat"]
        ready_at = now_utc + datetime.timedelta(seconds=cdef["grow_time_s"])
        row      = await queries.create_crop(parcel["id"], player_id, tx, ty, "wheat", ready_at)
        row["ready_at"] = ready_at
        self.crops[(tx, ty)] = dict(row)
        await self._send(player_id, {"type": "notice", "msg": "Planted wheat! Ready in ~20 min."})

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
            space   = player["bucket_cap"] - _bucket_total(player.get("bucket", {}))
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

        if self.season.tick():
            await queries.save_season_state(self.season.season)
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
            for t in self.towns.values():
                await queries.update_town(t)

    async def _do_resource_tick(self, elapsed: float):
        all_nodes = {**self.nodes, **self.structures}
        for node in all_nodes.values():
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
            for node in all_nodes.values():
                if node.get("is_market") or node.get("is_town_hall"):
                    continue
                if abs(px - node["x"]) > COLLECTION_RADIUS:
                    continue
                if abs(py - node["y"]) > COLLECTION_RADIUS:
                    continue
                cap   = player["bucket_cap"]
                load  = _bucket_total(player.get("bucket", {}))
                space = cap - load
                if space <= 0 or node["current_amount"] <= 0:
                    continue
                collected = min(COLLECTION_RATE, space, node["current_amount"])
                node["current_amount"] = max(0.0, node["current_amount"] - collected)
                rtype = node["node_type"]
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

    async def _broadcast_state(self):
        if not self.sockets:
            return
        all_players  = [
            {"id": p["id"], "username": p["username"], "x": p["x"], "y": p["y"],
             "flat_tire": p.get("flat_tire", 0)}
            for p in self.players.values() if p["id"] in self.sockets
        ]
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
            try:
                await ws.send_json({
                    "type":       "tick",
                    "players":    all_players,
                    "player":     self._player_wire(player),
                    "nodes":      nearby_nodes + all_structs,
                    "piles":      nearby_piles,
                    "crops":      nearby_crops,
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
        return {
            "id": p["id"], "x": p["x"], "y": p["y"],
            "coins": p["coins"], "bucket": p.get("bucket", {}),
            "bucket_cap": p["bucket_cap"], "pocket": p.get("pocket", {}),
            "wb_paint":  round(p.get("wb_paint",  100), 1),
            "wb_tire":   round(p.get("wb_tire",   100), 1),
            "wb_handle": round(p.get("wb_handle", 100), 1),
            "flat_tire": p.get("flat_tire", 0),
            "wb_bucket_level": p.get("wb_bucket_level", 1),
            "wb_tire_level":   p.get("wb_tire_level",   1),
            "wb_handle_level": p.get("wb_handle_level", 1),
            "wb_barrow_level": p.get("wb_barrow_level", 1),
        }

    def _node_wire(self, n: dict) -> dict:
        return {
            "id": n["id"], "x": n["x"], "y": n["y"],
            "type":         n["node_type"],
            "amount":       round(n["current_amount"], 1),
            "max":          n["max_amount"],
            "is_structure": n.get("is_structure", False),
            "is_market":    n.get("is_market", False),
            "is_town_hall": n.get("is_town_hall", False),
            "owner_name":   n.get("owner_name"),
            "owner_id":     n.get("owner_id"),
        }

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
        return {
            "x": c["x"], "y": c["y"],
            "crop_type":  c["crop_type"],
            "owner_id":   c["owner_id"],
            "ready":      ready_at <= now,
            "fertilized": c.get("fertilized_at") is not None,
        }

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
        return {
            "type":    "init",
            "player":  self._player_wire(player),
            "nodes":   nearby_nodes + [self._node_wire(n) for n in self.structures.values()],
            "parcels": [self._parcel_wire(p) for p in self.world_parcels.values()],
            "piles":   nearby_piles,
            "crops":   [self._crop_wire(c) for c in self.crops.values()],
            "market":  {"x": MARKET_TILE[0], "y": MARKET_TILE[1]},
            "npc_shops": [
                {"key": k, "x": v[0], "y": v[1], "label": NPC_SHOP_LABELS[k]}
                for k, v in NPC_SHOP_LOCATIONS.items()
            ],
            "towns":   [self._town_wire(t) for t in self.towns.values()],
            "prices":  self.prices,
            "season":  self.season.wire(),
            "world":   {"w": WORLD_W, "h": WORLD_H},
        }


engine = GameEngine()
