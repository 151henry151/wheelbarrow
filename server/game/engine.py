"""
In-memory game state. All mutation happens here; the DB handles persistence.
"""
import asyncio
import datetime
import time
import uuid
from typing import Optional

from fastapi import WebSocket

from server.game.constants import (
    WORLD_W, WORLD_H, COLLECTION_RADIUS, COLLECTION_RATE,
    MARKET_TILE, PARCEL_SIZE, LAND_PRICE, STRUCTURE_DEFS,
    MARKET_BASE_PRICES, MARKET_DRIFT_INTERVAL, MARKET_DRIFT_THRESHOLD,
    NPC_SHOP_LOCATIONS, NPC_SHOP_LABELS, NPC_SHOP_ADJACENCY,
    SEED_SHOP_ITEMS, CROP_DEFS,
    WB_BUCKET_CAP, WB_BUCKET_COST, WB_TIRE_FLAT_MULT, WB_TIRE_COST,
    WB_HANDLE_BREAK_MULT, WB_HANDLE_COST, WB_BARROW_DECAY_MULT, WB_BARROW_COST,
    REPAIR_COST_PER_PCT, REPAIR_FLAT_COST,
    UPGRADE_COMPONENTS,
)
from server.game.seasons import SeasonClock
from server.game.wb_condition import apply_move_decay, is_immobile
from server.db import queries


def _bucket_total(bucket: dict) -> float:
    return sum(bucket.values())

def _parcel_key(tile_x: int, tile_y: int) -> tuple:
    return (tile_x // PARCEL_SIZE, tile_y // PARCEL_SIZE)

def _parcel_origin(px: int, py: int) -> tuple:
    return (px * PARCEL_SIZE, py * PARCEL_SIZE)

def _near_shop(player: dict, shop_key: str) -> bool:
    sx, sy = NPC_SHOP_LOCATIONS[shop_key]
    return (abs(player["x"] - sx) <= NPC_SHOP_ADJACENCY and
            abs(player["y"] - sy) <= NPC_SHOP_ADJACENCY)


class GameEngine:
    def __init__(self):
        self.players:    dict[int, dict]     = {}
        self.sockets:    dict[int, WebSocket] = {}
        self.tokens:     dict[str, int]      = {}
        self.nodes:      dict[int, dict]     = {}   # wild resource nodes
        self.structures: dict[int, dict]     = {}   # player-built structures
        self.parcels:    dict[tuple, dict]   = {}   # (px,py) -> parcel
        self.prices:     dict[str, float]    = {}
        self.sales_volume: dict[str, float]  = {r: 0.0 for r in MARKET_BASE_PRICES}
        # Piles: (x,y) -> {resource_type: pile_dict}
        self.piles: dict[tuple, dict[str, dict]] = {}
        # Crops: (x,y) -> crop_dict
        self.crops: dict[tuple, dict] = {}
        # Season clock
        self.season: SeasonClock = SeasonClock()

        self._last_resource_tick = time.monotonic()
        self._last_persist       = time.monotonic()
        self._last_market_drift  = time.monotonic()

    # ------------------------------------------------------------------ setup

    async def load(self):
        for node in await queries.load_all_nodes():
            self.nodes[node["id"]] = dict(node)
        for parcel in await queries.load_all_parcels():
            key = _parcel_key(parcel["x"] * PARCEL_SIZE, parcel["y"] * PARCEL_SIZE)
            self.parcels[key] = dict(parcel)
        for struct in await queries.load_all_structures():
            self.structures[struct["id"]] = self._struct_to_node(struct)
        self.prices = await queries.get_market_prices()
        for pile in await queries.load_all_piles():
            key = (pile["x"], pile["y"])
            if key not in self.piles:
                self.piles[key] = {}
            self.piles[key][pile["resource_type"]] = dict(pile)
        for crop in await queries.load_all_crops():
            self.crops[(crop["x"], crop["y"])] = dict(crop)
        season_row = await queries.load_season_state()
        if season_row:
            self.season.load_from_db(season_row["season"], season_row["season_start"])

    def _struct_to_node(self, struct: dict) -> dict:
        sdef = STRUCTURE_DEFS.get(struct["structure_type"], {})
        return {
            "id":             struct["id"],
            "x":              struct["x"],
            "y":              struct["y"],
            "node_type":      sdef.get("produces") or "market",
            "structure_type": struct["structure_type"],
            "current_amount": 0.0,
            "max_amount":     sdef.get("max_amount", 0),
            "replenish_rate": sdef.get("replenish_rate", 0),
            "collect_fee":    sdef.get("collect_fee", 0),
            "owner_id":       struct["owner_id"],
            "owner_name":     struct["owner_name"],
            "is_structure":   True,
            "is_market":      sdef.get("is_market", False),
            "inventory":      struct.get("inventory", {}),
            "config":         struct.get("config", {}),
        }

    # ---------------------------------------------------------------- sessions

    def create_session(self, player: dict) -> str:
        token = str(uuid.uuid4())
        self.tokens[token] = player["id"]
        # Ensure new fields have defaults for legacy DB rows
        player.setdefault("pocket",          {})
        player.setdefault("wb_paint",        100.0)
        player.setdefault("wb_tire",         100.0)
        player.setdefault("wb_handle",       100.0)
        player.setdefault("flat_tire",       0)
        player.setdefault("wb_bucket_level", 1)
        player.setdefault("wb_tire_level",   1)
        player.setdefault("wb_handle_level", 1)
        player.setdefault("wb_barrow_level", 1)
        # Sync bucket_cap to upgrade level
        player["bucket_cap"] = WB_BUCKET_CAP.get(player["wb_bucket_level"], 10)
        self.players[player["id"]] = player
        return token

    def get_player_by_token(self, token: str) -> Optional[dict]:
        pid = self.tokens.get(token)
        return self.players.get(pid) if pid is not None else None

    def add_socket(self, player_id: int, ws: WebSocket):
        self.sockets[player_id] = ws

    async def remove_player(self, player_id: int):
        self.sockets.pop(player_id, None)
        player = self.players.get(player_id)
        if player:
            await queries.save_player(player)

    # ------------------------------------------------------------------ input

    async def handle_input(self, player_id: int, msg: dict):
        t = msg.get("type")
        if   t == "move":          self._move(player_id, msg.get("dir"))
        elif t == "sell":          await self._sell_npc_market(player_id)
        elif t == "buy_parcel":    await self._buy_parcel(player_id)
        elif t == "build":         await self._build(player_id, msg.get("structure_type"))
        elif t == "unload":        await self._unload(player_id)
        elif t == "set_pile_price":await self._set_pile_price(player_id, msg.get("resource_type"), msg.get("price"))
        elif t == "buy_pile":      await self._buy_pile(player_id, msg.get("resource_type"), msg.get("amount"))
        elif t == "npc_shop_buy":  await self._npc_shop_buy(player_id, msg.get("shop"), msg.get("item"))
        elif t == "repair":        await self._repair(player_id, msg.get("component"))
        elif t == "upgrade_wb":    await self._upgrade_wb(player_id, msg.get("component"))
        elif t == "farm":          await self._farm(player_id)
        elif t == "market_config": await self._market_config(player_id, msg.get("prices"))
        elif t == "market_trade":  await self._market_trade(player_id, msg.get("action"), msg.get("resource_type"), msg.get("amount"))

    # ---- movement -----------------------------------------------------------

    def _move(self, player_id: int, direction: str):
        player = self.players.get(player_id)
        if not player:
            return
        if is_immobile(player):
            asyncio.ensure_future(self._send(player_id, {
                "type": "notice",
                "msg": "Your handle is broken! Go to the Repair Shop (50,44).",
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
                asyncio.ensure_future(self._send(player_id, {
                    "type": "notice", "msg": "Flat tyre! Movement slowed. Repair Shop at (50,44).",
                }))
            elif ev == "handle_break":
                asyncio.ensure_future(self._send(player_id, {
                    "type": "notice", "msg": "Handle snapped! You can't move. Repair Shop at (50,44).",
                }))
            elif ev.startswith("spill:"):
                _, rtype, amt = ev.split(":")
                asyncio.ensure_future(self._send(player_id, {
                    "type": "notice", "msg": f"Hole in barrow! Spilled {amt} {rtype}.",
                }))

    # ---- sell at NPC market -------------------------------------------------

    async def _sell_npc_market(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        if (player["x"], player["y"]) != MARKET_TILE:
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

    async def _buy_parcel(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        key = _parcel_key(player["x"], player["y"])
        if key in self.parcels:
            await self._send(player_id, {"type": "notice", "msg": "This land is already owned."})
            return
        if player["coins"] < LAND_PRICE:
            await self._send(player_id, {"type": "notice", "msg": f"Need {LAND_PRICE} coins to buy land."})
            return
        player["coins"] -= LAND_PRICE
        parcel = await queries.create_parcel(player_id, key[0], key[1])
        parcel["owner_name"] = player["username"]
        self.parcels[key] = parcel
        await self._send(player_id, {
            "type":   "parcel_bought",
            "parcel": self._parcel_wire(parcel),
            "coins":  player["coins"],
        })

    # ---- build --------------------------------------------------------------

    async def _build(self, player_id: int, structure_type: str):
        player = self.players.get(player_id)
        if not player or structure_type not in STRUCTURE_DEFS:
            return
        key    = _parcel_key(player["x"], player["y"])
        parcel = self.parcels.get(key)
        if not parcel or parcel["owner_id"] != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only build on your own land."})
            return
        tx, ty = player["x"], player["y"]
        for n in {**self.nodes, **self.structures}.values():
            if n["x"] == tx and n["y"] == ty:
                await self._send(player_id, {"type": "notice", "msg": "Something is already here."})
                return
        sdef = STRUCTURE_DEFS[structure_type]
        if player["coins"] < sdef["cost_coins"]:
            await self._send(player_id, {"type": "notice", "msg": f"Need {sdef['cost_coins']} coins."})
            return
        for rtype, amt in sdef["cost_resources"].items():
            if player["bucket"].get(rtype, 0) < amt:
                await self._send(player_id, {"type": "notice", "msg": f"Need {amt} {rtype} in bucket."})
                return
        player["coins"] -= sdef["cost_coins"]
        for rtype, amt in sdef["cost_resources"].items():
            player["bucket"][rtype] = round(player["bucket"].get(rtype, 0) - amt, 2)
            if player["bucket"][rtype] <= 0:
                del player["bucket"][rtype]
        struct_row = await queries.create_structure(parcel["id"], tx, ty, structure_type)
        node = self._struct_to_node(struct_row)
        self.structures[node["id"]] = node
        await self._send(player_id, {
            "type":      "built",
            "structure": self._node_wire(node),
            "coins":     player["coins"],
        })

    # ---- unload bucket to pile ----------------------------------------------

    async def _unload(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        key = _parcel_key(player["x"], player["y"])
        parcel = self.parcels.get(key)
        if not parcel or parcel["owner_id"] != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only pile resources on your own land."})
            return
        bucket = player.get("bucket", {})
        if not bucket:
            await self._send(player_id, {"type": "notice", "msg": "Your bucket is empty."})
            return
        tx, ty = player["x"], player["y"]
        pile_key = (tx, ty)
        if pile_key not in self.piles:
            self.piles[pile_key] = {}
        total_added = 0.0
        for rtype, amt in list(bucket.items()):
            if amt <= 0:
                continue
            existing = self.piles[pile_key].get(rtype, {})
            new_amt  = round(existing.get("amount", 0.0) + amt, 2)
            pile_row = await queries.upsert_pile(
                parcel["id"], player_id, tx, ty, rtype, new_amt,
                existing.get("sell_price"),
            )
            self.piles[pile_key][rtype] = dict(pile_row)
            total_added += amt
        player["bucket"] = {}
        await self._send(player_id, {
            "type":  "notice",
            "msg":   f"Unloaded {round(total_added,1)} units onto land. Press [E] to set a sale price.",
        })

    # ---- set pile sell price ------------------------------------------------

    async def _set_pile_price(self, player_id: int, resource_type: str, price):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty  = player["x"], player["y"]
        pile_key = (tx, ty)
        pile_map = self.piles.get(pile_key, {})
        if resource_type not in pile_map:
            await self._send(player_id, {"type": "notice", "msg": "No pile of that type here."})
            return
        pile = pile_map[resource_type]
        if pile.get("owner_id") != player_id:
            await self._send(player_id, {"type": "notice", "msg": "Not your pile."})
            return
        sell_price = None if price is None else max(0.0, float(price))
        pile_row = await queries.upsert_pile(
            pile["parcel_id"], player_id, tx, ty,
            resource_type, pile["amount"], sell_price,
        )
        self.piles[pile_key][resource_type] = dict(pile_row)
        price_str = f"{sell_price}c/unit" if sell_price is not None else "not for sale"
        await self._send(player_id, {"type": "notice", "msg": f"{resource_type} pile: {price_str}"})

    # ---- buy from player pile -----------------------------------------------

    async def _buy_pile(self, player_id: int, resource_type: str, amount: float):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty   = player["x"], player["y"]
        pile_key = (tx, ty)
        pile_map = self.piles.get(pile_key, {})
        pile     = pile_map.get(resource_type)

        if not pile:
            await self._send(player_id, {"type": "notice", "msg": "No pile here."})
            return
        if pile.get("sell_price") is None:
            await self._send(player_id, {"type": "notice", "msg": "That pile isn't for sale."})
            return
        if pile.get("owner_id") == player_id:
            await self._send(player_id, {"type": "notice", "msg": "That's your own pile."})
            return

        bucket    = player.get("bucket", {})
        space     = player["bucket_cap"] - _bucket_total(bucket)
        can_buy   = min(float(amount), space, pile["amount"])
        if can_buy <= 0:
            await self._send(player_id, {"type": "notice", "msg": "No space in your bucket." if space <= 0 else "Pile is empty."})
            return
        total_cost = round(can_buy * pile["sell_price"], 2)
        if player["coins"] < total_cost:
            can_afford = player["coins"] / pile["sell_price"]
            can_buy    = min(can_buy, can_afford)
            total_cost = round(can_buy * pile["sell_price"], 2)
        if can_buy <= 0:
            await self._send(player_id, {"type": "notice", "msg": "Can't afford any."})
            return

        can_buy = round(can_buy, 2)
        player["coins"]          -= int(total_cost)
        bucket[resource_type]     = round(bucket.get(resource_type, 0) + can_buy, 2)
        pile["amount"]             = round(pile["amount"] - can_buy, 2)

        # Pay the owner
        owner = self.players.get(pile["owner_id"])
        if owner:
            owner["coins"] += int(total_cost)

        if pile["amount"] <= 0:
            del self.piles[pile_key][resource_type]
            await queries.delete_pile(tx, ty, resource_type)
        else:
            await queries.upsert_pile(
                pile["parcel_id"], pile["owner_id"], tx, ty,
                resource_type, pile["amount"], pile["sell_price"],
            )
        await self._send(player_id, {
            "type":  "sold",
            "earned": -int(total_cost),
            "coins":  player["coins"],
            "msg":    f"Bought {round(can_buy,1)} {resource_type} for {int(total_cost)}c.",
        })

    # ---- NPC shop buying ----------------------------------------------------

    async def _npc_shop_buy(self, player_id: int, shop: str, item: str):
        player = self.players.get(player_id)
        if not player:
            return
        if shop not in NPC_SHOP_LOCATIONS:
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
        player = self.players.get(player_id)
        catalog = SEED_SHOP_ITEMS.get(item)
        if not catalog:
            return
        if player["coins"] < catalog["cost"]:
            await self._send(player_id, {"type": "notice", "msg": f"Need {catalog['cost']}c."})
            return
        player["coins"] -= catalog["cost"]
        pocket = player.setdefault("pocket", {})
        pocket[item] = pocket.get(item, 0) + catalog["qty"]
        await self._send(player_id, {
            "type":  "notice",
            "msg":   f"Bought {catalog['label']} for {catalog['cost']}c.",
        })

    async def _general_store_buy(self, player_id: int, item: str):
        """
        item format: "bucket_2", "tire_3", "handle_4", "barrow_5" etc.
        """
        player = self.players.get(player_id)
        if not item or "_" not in item:
            return
        component, _, level_s = item.partition("_")
        try:
            target_level = int(level_s)
        except ValueError:
            return

        level_key = f"wb_{component}_level"
        cost_map  = {"bucket": WB_BUCKET_COST, "tire": WB_TIRE_COST,
                     "handle": WB_HANDLE_COST, "barrow": WB_BARROW_COST}.get(component)
        if not cost_map:
            return
        current_level = player.get(level_key, 1)
        if target_level != current_level + 1:
            await self._send(player_id, {"type": "notice", "msg": "Upgrade one level at a time."})
            return
        if target_level not in cost_map:
            await self._send(player_id, {"type": "notice", "msg": "Already at max level."})
            return
        cost = cost_map[target_level]
        if player["coins"] < cost:
            await self._send(player_id, {"type": "notice", "msg": f"Need {cost}c."})
            return
        player["coins"] -= cost
        player[level_key] = target_level
        if component == "bucket":
            player["bucket_cap"] = WB_BUCKET_CAP.get(target_level, player["bucket_cap"])
        comp_label = UPGRADE_COMPONENTS.get(component, (None,None,component))[2]
        await self._send(player_id, {
            "type":  "notice",
            "msg":   f"{comp_label} upgraded to level {target_level}!",
        })

    # ---- repair -------------------------------------------------------------

    async def _repair(self, player_id: int, component: str):
        player = self.players.get(player_id)
        if not player:
            return
        if not _near_shop(player, "repair_shop"):
            await self._send(player_id, {"type": "notice", "msg": "Move closer to the Repair Shop (50,44)."})
            return

        if component == "flat":
            if not player.get("flat_tire"):
                await self._send(player_id, {"type": "notice", "msg": "Tyre isn't flat."})
                return
            if player["coins"] < REPAIR_FLAT_COST:
                await self._send(player_id, {"type": "notice", "msg": f"Need {REPAIR_FLAT_COST}c to fix flat."})
                return
            player["coins"]    -= REPAIR_FLAT_COST
            player["flat_tire"] = 0
            await self._send(player_id, {"type": "notice", "msg": f"Flat tyre fixed for {REPAIR_FLAT_COST}c."})
            return

        if component not in REPAIR_COST_PER_PCT:
            return
        cond_key  = f"wb_{component}"
        current   = player.get(cond_key, 100.0)
        missing   = 100.0 - current
        if missing <= 0:
            await self._send(player_id, {"type": "notice", "msg": f"{component} is already at 100%."})
            return
        cost = round(missing * REPAIR_COST_PER_PCT[component])
        if player["coins"] < cost:
            # Partial repair
            can_restore = player["coins"] / REPAIR_COST_PER_PCT[component]
            player[cond_key]  = min(100.0, current + can_restore)
            player["coins"]   = 0
            await self._send(player_id, {"type": "notice", "msg": f"Partial repair (ran out of coins). {component}: {round(player[cond_key])}%"})
            return
        player["coins"]  -= cost
        player[cond_key]  = 100.0
        await self._send(player_id, {"type": "notice", "msg": f"{component} fully repaired for {cost}c."})

    # ---- upgrade WB (alias used by client interaction flow) ----------------

    async def _upgrade_wb(self, player_id: int, component: str):
        """Shortcut: upgrade to next level."""
        player = self.players.get(player_id)
        if not player:
            return
        if not _near_shop(player, "general_store"):
            await self._send(player_id, {"type": "notice", "msg": "Move closer to the General Store (44,50)."})
            return
        level_key = f"wb_{component}_level"
        current   = player.get(level_key, 1)
        await self._general_store_buy(player_id, f"{component}_{current + 1}")

    # ---- farming ------------------------------------------------------------

    async def _farm(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty   = player["x"], player["y"]
        key      = _parcel_key(tx, ty)
        parcel   = self.parcels.get(key)
        crop_key = (tx, ty)
        existing = self.crops.get(crop_key)

        if existing and not existing["harvested"]:
            # Try fertilize or harvest
            import datetime
            now_utc = datetime.datetime.utcnow()
            ready_at = existing["ready_at"]
            if isinstance(ready_at, str):
                ready_at = datetime.datetime.fromisoformat(ready_at)

            if ready_at <= now_utc:
                # Harvest
                if parcel and parcel["owner_id"] == player_id:
                    cdef = CROP_DEFS.get(existing["crop_type"], CROP_DEFS["wheat"])
                    is_fert = existing.get("fertilized_at") is not None
                    harvested_qty = cdef["yield_fertilized"] if is_fert else cdef["yield_base"]
                    space = player["bucket_cap"] - _bucket_total(player.get("bucket", {}))
                    can_take = min(harvested_qty, space)
                    if can_take <= 0:
                        await self._send(player_id, {"type": "notice", "msg": "No space in bucket to harvest."})
                        return
                    player.setdefault("bucket", {})[existing["crop_type"]] = round(
                        player["bucket"].get(existing["crop_type"], 0) + can_take, 2
                    )
                    existing["harvested"] = 1
                    del self.crops[crop_key]
                    await queries.harvest_crop(existing["id"])
                    await self._send(player_id, {"type": "notice", "msg": f"Harvested {round(can_take,1)} {existing['crop_type']}!"})
                    return

            # Try fertilize
            pocket = player.get("pocket", {})
            if not existing.get("fertilized_at") and pocket.get("fertilizer", 0) > 0:
                planted_at = existing["planted_at"]
                if isinstance(planted_at, str):
                    planted_at = datetime.datetime.fromisoformat(planted_at)
                elapsed = (now_utc - planted_at).total_seconds()
                cdef = CROP_DEFS.get(existing["crop_type"], CROP_DEFS["wheat"])
                if elapsed <= cdef["fertilize_window_s"]:
                    pocket["fertilizer"] -= 1
                    if pocket["fertilizer"] <= 0:
                        del pocket["fertilizer"]
                    new_ready = now_utc + datetime.timedelta(seconds=cdef["grow_time_fert_s"] - elapsed)
                    existing["fertilized_at"] = now_utc.isoformat()
                    existing["ready_at"]       = new_ready
                    await queries.fertilize_crop(existing["id"], new_ready)
                    await self._send(player_id, {"type": "notice", "msg": "Fertilized! Crop grows faster."})
                    return
                else:
                    await self._send(player_id, {"type": "notice", "msg": "Too late to fertilize (window passed)."})
                    return

            mins = max(0, int((ready_at - now_utc).total_seconds() // 60))
            fert_str = " (fertilized)" if existing.get("fertilized_at") else ""
            await self._send(player_id, {"type": "notice", "msg": f"Crop growing{fert_str}. ~{mins} min until harvest."})
            return

        # Plant
        if not parcel or parcel["owner_id"] != player_id:
            await self._send(player_id, {"type": "notice", "msg": "You can only farm on your own land."})
            return
        pocket = player.setdefault("pocket", {})
        if pocket.get("wheat_seed", 0) <= 0:
            await self._send(player_id, {"type": "notice", "msg": "No wheat seeds. Buy from Seed Shop (56,50)."})
            return
        # Check nothing blocking this tile
        for n in {**self.nodes, **self.structures}.values():
            if n["x"] == tx and n["y"] == ty:
                await self._send(player_id, {"type": "notice", "msg": "Something else is here."})
                return

        pocket["wheat_seed"] -= 1
        if pocket["wheat_seed"] <= 0:
            del pocket["wheat_seed"]

        import datetime
        now_utc  = datetime.datetime.utcnow()
        cdef     = CROP_DEFS["wheat"]
        ready_at = now_utc + datetime.timedelta(seconds=cdef["grow_time_s"])
        crop_row = await queries.create_crop(parcel["id"], player_id, tx, ty, "wheat", ready_at)
        crop_row["ready_at"] = ready_at
        self.crops[crop_key]  = dict(crop_row)
        await self._send(player_id, {"type": "notice", "msg": "Planted wheat! Ready in ~20 min."})

    # ---- player market config -----------------------------------------------

    async def _market_config(self, player_id: int, prices: dict):
        """Owner sets buy/sell prices in their player market."""
        player = self.players.get(player_id)
        if not player or not isinstance(prices, dict):
            return
        tx, ty = player["x"], player["y"]
        market_node = None
        for n in self.structures.values():
            if n.get("is_market") and n["x"] == tx and n["y"] == ty and n["owner_id"] == player_id:
                market_node = n
                break
        if not market_node:
            await self._send(player_id, {"type": "notice", "msg": "Stand on your Player Market to configure it."})
            return
        market_node["config"]["prices"] = prices
        await queries.save_structure(market_node)
        await self._send(player_id, {"type": "notice", "msg": "Market prices updated."})

    # ---- trade at player market ---------------------------------------------

    async def _market_trade(self, player_id: int, action: str, resource_type: str, amount: float):
        """Buy or sell at a nearby player market."""
        player = self.players.get(player_id)
        if not player:
            return
        tx, ty = player["x"], player["y"]
        market_node = None
        for n in self.structures.values():
            if n.get("is_market") and abs(n["x"] - tx) <= 1 and abs(n["y"] - ty) <= 1:
                market_node = n
                break
        if not market_node:
            await self._send(player_id, {"type": "notice", "msg": "No player market nearby."})
            return
        cfg = market_node.get("config", {})
        prices = cfg.get("prices", {})
        price = prices.get(resource_type)
        if price is None:
            await self._send(player_id, {"type": "notice", "msg": f"Market doesn't trade {resource_type}."})
            return

        owner = self.players.get(market_node["owner_id"])
        inventory = market_node.setdefault("inventory", {})

        if action == "sell":
            # Player sells to market
            bucket = player.get("bucket", {})
            avail  = bucket.get(resource_type, 0)
            qty    = min(float(amount), avail)
            if qty <= 0:
                await self._send(player_id, {"type": "notice", "msg": f"No {resource_type} to sell."})
                return
            earned = round(qty * price)
            if owner and owner["coins"] < earned:
                await self._send(player_id, {"type": "notice", "msg": "Market owner doesn't have enough coins."})
                return
            bucket[resource_type] = round(avail - qty, 2)
            if bucket[resource_type] <= 0:
                del bucket[resource_type]
            player["coins"]  += earned
            inventory[resource_type] = round(inventory.get(resource_type, 0) + qty, 2)
            if owner:
                owner["coins"] -= earned
            await self._send(player_id, {"type": "sold", "earned": earned, "coins": player["coins"]})

        elif action == "buy":
            # Player buys from market
            inv_qty = inventory.get(resource_type, 0)
            space   = player["bucket_cap"] - _bucket_total(player.get("bucket", {}))
            qty     = min(float(amount), inv_qty, space)
            if qty <= 0:
                await self._send(player_id, {"type": "notice", "msg": "Not enough in market or no bucket space."})
                return
            total_cost = round(qty * price)
            if player["coins"] < total_cost:
                qty        = player["coins"] / price
                total_cost = round(qty * price)
            if qty <= 0:
                await self._send(player_id, {"type": "notice", "msg": "Can't afford any."})
                return
            qty = round(qty, 2)
            player["coins"] -= total_cost
            bucket = player.setdefault("bucket", {})
            bucket[resource_type] = round(bucket.get(resource_type, 0) + qty, 2)
            inventory[resource_type] = round(inventory.get(resource_type, 0) - qty, 2)
            if owner:
                owner["coins"] += total_cost
            await self._send(player_id, {
                "type":   "notice",
                "msg":    f"Bought {round(qty,1)} {resource_type} for {total_cost}c.",
            })

        await queries.save_structure(market_node)

    # ------------------------------------------------------------------- tick

    async def tick(self, resource_tick_s: int, persist_interval_s: int):
        now = time.monotonic()

        # Season
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

        await self._broadcast_state()

        if now - self._last_persist >= persist_interval_s:
            self._last_persist = now
            for p in self.players.values():
                if p["id"] in self.sockets:
                    await queries.save_player(p)
            for n in self.nodes.values():
                await queries.save_node(n)

    async def _do_resource_tick(self, elapsed: float):
        all_nodes = {**self.nodes, **self.structures}
        for node in all_nodes.values():
            if node.get("is_market"):
                continue
            node["current_amount"] = min(
                node["max_amount"],
                node["current_amount"] + node["replenish_rate"] * elapsed,
            )

        for player in self.players.values():
            if player["id"] not in self.sockets:
                continue
            for node in all_nodes.values():
                if node.get("is_market"):
                    continue
                if abs(player["x"] - node["x"]) > COLLECTION_RADIUS:
                    continue
                if abs(player["y"] - node["y"]) > COLLECTION_RADIUS:
                    continue
                cap       = player["bucket_cap"]
                load      = _bucket_total(player.get("bucket", {}))
                space     = cap - load
                if space <= 0 or node["current_amount"] <= 0:
                    continue
                collected = min(COLLECTION_RATE, space, node["current_amount"])
                node["current_amount"] = max(0.0, node["current_amount"] - collected)
                rtype = node["node_type"]
                player.setdefault("bucket", {})[rtype] = round(
                    player["bucket"].get(rtype, 0) + collected, 2
                )
                if node.get("is_structure"):
                    owner_id = node["owner_id"]
                    fee      = node.get("collect_fee", 1)
                    owner    = self.players.get(owner_id)
                    if owner and owner_id != player["id"]:
                        owner["coins"] += fee

    async def _do_market_drift(self):
        for rtype, base in MARKET_BASE_PRICES.items():
            sold    = self.sales_volume.get(rtype, 0.0)
            current = self.prices.get(rtype, base)
            if sold >= MARKET_DRIFT_THRESHOLD:
                new_price = max(round(base * 0.5, 2), round(current * 0.85, 2))
            else:
                new_price = min(round(base * 2.0, 2), round(current * 1.10, 2))
            self.prices[rtype]            = new_price
            self.sales_volume[rtype]      = 0.0
        await queries.update_market_prices(self.prices)

    async def _broadcast_state(self):
        if not self.sockets:
            return
        all_players = [
            {"id": p["id"], "username": p["username"], "x": p["x"], "y": p["y"],
             "flat_tire": p.get("flat_tire", 0)}
            for p in self.players.values() if p["id"] in self.sockets
        ]
        all_nodes   = ([self._node_wire(n) for n in self.nodes.values()] +
                       [self._node_wire(n) for n in self.structures.values()])
        all_parcels = [self._parcel_wire(p) for p in self.parcels.values()]
        all_piles   = [self._pile_wire(pile, rtype)
                       for pmap in self.piles.values()
                       for rtype, pile in pmap.items()]
        all_crops   = [self._crop_wire(c) for c in self.crops.values()]
        season_wire = self.season.wire()

        for pid, ws in list(self.sockets.items()):
            player = self.players.get(pid)
            if not player:
                continue
            try:
                await ws.send_json({
                    "type":    "tick",
                    "players": all_players,
                    "player":  self._player_wire(player),
                    "nodes":   all_nodes,
                    "parcels": all_parcels,
                    "piles":   all_piles,
                    "crops":   all_crops,
                    "prices":  self.prices,
                    "season":  season_wire,
                })
            except Exception:
                pass

    async def _broadcast_all(self, msg: dict):
        for ws in list(self.sockets.values()):
            try:
                await ws.send_json(msg)
            except Exception:
                pass

    # ----------------------------------------------------------------- helpers

    async def _send(self, player_id: int, msg: dict):
        ws = self.sockets.get(player_id)
        if ws:
            try:
                await ws.send_json(msg)
            except Exception:
                pass

    def _player_wire(self, p: dict) -> dict:
        return {
            "id":              p["id"],
            "x":               p["x"],
            "y":               p["y"],
            "coins":           p["coins"],
            "bucket":          p.get("bucket", {}),
            "bucket_cap":      p["bucket_cap"],
            "pocket":          p.get("pocket", {}),
            "wb_paint":        round(p.get("wb_paint",  100), 1),
            "wb_tire":         round(p.get("wb_tire",   100), 1),
            "wb_handle":       round(p.get("wb_handle", 100), 1),
            "flat_tire":       p.get("flat_tire", 0),
            "wb_bucket_level": p.get("wb_bucket_level", 1),
            "wb_tire_level":   p.get("wb_tire_level",   1),
            "wb_handle_level": p.get("wb_handle_level", 1),
            "wb_barrow_level": p.get("wb_barrow_level", 1),
        }

    def _node_wire(self, n: dict) -> dict:
        return {
            "id":           n["id"],
            "x":            n["x"],
            "y":            n["y"],
            "type":         n["node_type"],
            "amount":       round(n["current_amount"], 1),
            "max":          n["max_amount"],
            "is_structure": n.get("is_structure", False),
            "is_market":    n.get("is_market", False),
            "owner_name":   n.get("owner_name"),
            "owner_id":     n.get("owner_id"),
        }

    def _parcel_wire(self, p: dict) -> dict:
        return {
            "px":         p["x"],
            "py":         p["y"],
            "owner_id":   p["owner_id"],
            "owner_name": p["owner_name"],
        }

    def _pile_wire(self, pile: dict, rtype: str) -> dict:
        return {
            "x":            pile["x"],
            "y":            pile["y"],
            "resource_type": rtype,
            "amount":       round(pile["amount"], 1),
            "sell_price":   pile.get("sell_price"),
            "owner_id":     pile.get("owner_id"),
        }

    def _crop_wire(self, c: dict) -> dict:
        import datetime
        now     = datetime.datetime.utcnow()
        ready_at = c["ready_at"]
        if isinstance(ready_at, str):
            ready_at = datetime.datetime.fromisoformat(ready_at)
        return {
            "x":          c["x"],
            "y":          c["y"],
            "crop_type":  c["crop_type"],
            "owner_id":   c["owner_id"],
            "ready":      ready_at <= now,
            "fertilized": c.get("fertilized_at") is not None,
        }

    def full_state(self, player_id: int) -> dict:
        player = self.players[player_id]
        all_piles = [self._pile_wire(pile, rtype)
                     for pmap in self.piles.values()
                     for rtype, pile in pmap.items()]
        return {
            "type":    "init",
            "player":  self._player_wire(player),
            "nodes":   ([self._node_wire(n) for n in self.nodes.values()] +
                        [self._node_wire(n) for n in self.structures.values()]),
            "parcels": [self._parcel_wire(p) for p in self.parcels.values()],
            "piles":   all_piles,
            "crops":   [self._crop_wire(c) for c in self.crops.values()],
            "market":  {"x": MARKET_TILE[0], "y": MARKET_TILE[1]},
            "npc_shops": [
                {"key": k, "x": v[0], "y": v[1], "label": NPC_SHOP_LABELS[k]}
                for k, v in NPC_SHOP_LOCATIONS.items()
            ],
            "prices":  self.prices,
            "season":  self.season.wire(),
            "world":   {"w": WORLD_W, "h": WORLD_H},
        }


engine = GameEngine()
