"""
In-memory game state. All mutation happens here; the DB handles persistence.
"""
import asyncio
import time
import uuid
from typing import Optional

from fastapi import WebSocket

from server.game.constants import (
    WORLD_W, WORLD_H, COLLECTION_RADIUS, COLLECTION_RATE,
    MARKET_TILE, PARCEL_SIZE, LAND_PRICE, STRUCTURE_DEFS,
    MARKET_BASE_PRICES, MARKET_DRIFT_INTERVAL, MARKET_DRIFT_THRESHOLD,
)
from server.db import queries


def _bucket_total(bucket: dict) -> float:
    return sum(bucket.values())

def _parcel_key(tile_x: int, tile_y: int) -> tuple:
    return (tile_x // PARCEL_SIZE, tile_y // PARCEL_SIZE)

def _parcel_origin(px: int, py: int) -> tuple:
    return (px * PARCEL_SIZE, py * PARCEL_SIZE)


class GameEngine:
    def __init__(self):
        self.players: dict[int, dict]    = {}
        self.sockets: dict[int, WebSocket] = {}
        self.tokens:  dict[str, int]     = {}
        self.nodes:   dict[int, dict]    = {}   # wild resource nodes
        self.structures: dict[int, dict] = {}   # player-built nodes (keyed by structure id)
        self.parcels: dict[tuple, dict]  = {}   # (parcel_x, parcel_y) -> parcel info
        self.prices:  dict[str, float]   = {}
        self.sales_volume: dict[str, float] = {r: 0.0 for r in MARKET_BASE_PRICES}

        self._last_resource_tick  = time.monotonic()
        self._last_persist        = time.monotonic()
        self._last_market_drift   = time.monotonic()

    # ------------------------------------------------------------------ setup

    async def load(self):
        for node in await queries.load_all_nodes():
            self.nodes[node["id"]] = dict(node)
        for parcel in await queries.load_all_parcels():
            self.parcels[_parcel_key(parcel["x"] * PARCEL_SIZE, parcel["y"] * PARCEL_SIZE)] = dict(parcel)
        for struct in await queries.load_all_structures():
            self.structures[struct["id"]] = self._struct_to_node(struct)
        self.prices = await queries.get_market_prices()

    def _struct_to_node(self, struct: dict) -> dict:
        sdef = STRUCTURE_DEFS.get(struct["structure_type"], {})
        return {
            "id":              struct["id"],
            "x":               struct["x"],
            "y":               struct["y"],
            "node_type":       sdef.get("produces", "unknown"),
            "structure_type":  struct["structure_type"],
            "current_amount":  0.0,
            "max_amount":      sdef.get("max_amount", 100),
            "replenish_rate":  sdef.get("replenish_rate", 0.5),
            "collect_fee":     sdef.get("collect_fee", 1),
            "owner_id":        struct["owner_id"],
            "owner_name":      struct["owner_name"],
            "is_structure":    True,
        }

    # ---------------------------------------------------------------- sessions

    def create_session(self, player: dict) -> str:
        token = str(uuid.uuid4())
        self.tokens[token] = player["id"]
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
        if   t == "move":        self._move(player_id, msg.get("dir"))
        elif t == "sell":        await self._sell(player_id)
        elif t == "buy_parcel":  await self._buy_parcel(player_id)
        elif t == "build":       await self._build(player_id, msg.get("structure_type"))

    def _move(self, player_id: int, direction: str):
        player = self.players.get(player_id)
        if not player:
            return
        dx, dy = {"up":(0,-1), "down":(0,1), "left":(-1,0), "right":(1,0)}.get(direction, (0,0))
        nx, ny = player["x"] + dx, player["y"] + dy
        if 0 <= nx < WORLD_W and 0 <= ny < WORLD_H:
            player["x"], player["y"] = nx, ny

    async def _sell(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        if (player["x"], player["y"]) != MARKET_TILE:
            return
        bucket = player.get("bucket", {})
        if not bucket:
            return
        earned = 0
        for rtype, amount in bucket.items():
            price = self.prices.get(rtype, 0)
            earned += int(amount) * price
            self.sales_volume[rtype] = self.sales_volume.get(rtype, 0) + amount
        player["coins"] += int(earned)
        player["bucket"] = {}
        ws = self.sockets.get(player_id)
        if ws:
            await ws.send_json({"type": "sold", "earned": int(earned), "coins": player["coins"]})

    async def _buy_parcel(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        key = _parcel_key(player["x"], player["y"])
        ws  = self.sockets.get(player_id)

        if key in self.parcels:
            if ws:
                await ws.send_json({"type": "notice", "msg": "This land is already owned."})
            return
        if player["coins"] < LAND_PRICE:
            if ws:
                await ws.send_json({"type": "notice", "msg": f"Need {LAND_PRICE} coins to buy land."})
            return

        player["coins"] -= LAND_PRICE
        parcel = await queries.create_parcel(player_id, key[0], key[1])
        parcel["owner_name"] = player["username"]
        self.parcels[key] = parcel
        if ws:
            await ws.send_json({
                "type": "parcel_bought",
                "parcel": self._parcel_wire(parcel),
                "coins": player["coins"],
            })

    async def _build(self, player_id: int, structure_type: str):
        player = self.players.get(player_id)
        if not player or structure_type not in STRUCTURE_DEFS:
            return
        ws  = self.sockets.get(player_id)
        key = _parcel_key(player["x"], player["y"])

        parcel = self.parcels.get(key)
        if not parcel or parcel["owner_id"] != player_id:
            if ws: await ws.send_json({"type": "notice", "msg": "You can only build on your own land."})
            return

        # Check tile not already occupied
        tx, ty = player["x"], player["y"]
        for n in {**self.nodes, **self.structures}.values():
            if n["x"] == tx and n["y"] == ty:
                if ws: await ws.send_json({"type": "notice", "msg": "Something is already here."})
                return

        sdef = STRUCTURE_DEFS[structure_type]
        if player["coins"] < sdef["cost_coins"]:
            if ws: await ws.send_json({"type": "notice", "msg": f"Need {sdef['cost_coins']} coins."})
            return
        for rtype, amt in sdef["cost_resources"].items():
            if player["bucket"].get(rtype, 0) < amt:
                if ws: await ws.send_json({"type": "notice", "msg": f"Need {amt} {rtype}."})
                return

        player["coins"] -= sdef["cost_coins"]
        for rtype, amt in sdef["cost_resources"].items():
            player["bucket"][rtype] = round(player["bucket"].get(rtype, 0) - amt, 2)
            if player["bucket"][rtype] <= 0:
                del player["bucket"][rtype]

        struct_row = await queries.create_structure(parcel["id"], tx, ty, structure_type)
        node = self._struct_to_node(struct_row)
        self.structures[node["id"]] = node

        if ws:
            await ws.send_json({
                "type":    "built",
                "structure": self._node_wire(node),
                "coins":   player["coins"],
            })

    # ------------------------------------------------------------------- tick

    async def tick(self, resource_tick_s: int, persist_interval_s: int):
        now = time.monotonic()

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
            node["current_amount"] = min(
                node["max_amount"],
                node["current_amount"] + node["replenish_rate"] * elapsed,
            )

        for player in self.players.values():
            if player["id"] not in self.sockets:
                continue
            for node in all_nodes.values():
                if abs(player["x"] - node["x"]) > COLLECTION_RADIUS:
                    continue
                if abs(player["y"] - node["y"]) > COLLECTION_RADIUS:
                    continue
                cap   = player["bucket_cap"]
                load  = _bucket_total(player["bucket"])
                space = cap - load
                if space <= 0 or node["current_amount"] <= 0:
                    continue
                collected = min(COLLECTION_RATE, space, node["current_amount"])
                node["current_amount"] = max(0.0, node["current_amount"] - collected)
                rtype = node["node_type"]
                player["bucket"][rtype] = round(player["bucket"].get(rtype, 0) + collected, 2)

                # Pay the structure owner
                if node.get("is_structure"):
                    owner_id  = node["owner_id"]
                    fee       = node.get("collect_fee", 1)
                    owner     = self.players.get(owner_id)
                    if owner and owner_id != player["id"]:
                        owner["coins"] += fee

    async def _do_market_drift(self):
        for rtype, base in MARKET_BASE_PRICES.items():
            sold    = self.sales_volume.get(rtype, 0.0)
            current = self.prices.get(rtype, base)
            if sold >= MARKET_DRIFT_THRESHOLD:
                new_price = max(round(base * 0.5, 2), round(current * 0.85, 2))
            else:
                new_price = min(round(base * 2.0, 2), round(current * 1.1, 2))
            self.prices[rtype] = new_price
            self.sales_volume[rtype] = 0.0
        await queries.update_market_prices(self.prices)

    async def _broadcast_state(self):
        if not self.sockets:
            return
        all_players = [
            {"id": p["id"], "username": p["username"], "x": p["x"], "y": p["y"]}
            for p in self.players.values() if p["id"] in self.sockets
        ]
        all_nodes = [self._node_wire(n) for n in self.nodes.values()] + \
                    [self._node_wire(n) for n in self.structures.values()]
        all_parcels = [self._parcel_wire(p) for p in self.parcels.values()]

        for pid, ws in list(self.sockets.items()):
            player = self.players.get(pid)
            if not player:
                continue
            try:
                await ws.send_json({
                    "type":    "tick",
                    "players": all_players,
                    "player":  {
                        "id":         player["id"],
                        "x":          player["x"],
                        "y":          player["y"],
                        "coins":      player["coins"],
                        "bucket":     player["bucket"],
                        "bucket_cap": player["bucket_cap"],
                    },
                    "nodes":   all_nodes,
                    "parcels": all_parcels,
                    "prices":  self.prices,
                })
            except Exception:
                pass

    # ----------------------------------------------------------------- helpers

    def _node_wire(self, n: dict) -> dict:
        return {
            "id":          n["id"],
            "x":           n["x"],
            "y":           n["y"],
            "type":        n["node_type"],
            "amount":      round(n["current_amount"], 1),
            "max":         n["max_amount"],
            "is_structure": n.get("is_structure", False),
            "owner_name":  n.get("owner_name"),
        }

    def _parcel_wire(self, p: dict) -> dict:
        return {
            "px":         p["x"],
            "py":         p["y"],
            "owner_id":   p["owner_id"],
            "owner_name": p["owner_name"],
        }

    def full_state(self, player_id: int) -> dict:
        player = self.players[player_id]
        return {
            "type":    "init",
            "player":  {
                "id":         player["id"],
                "username":   player["username"],
                "x":          player["x"],
                "y":          player["y"],
                "coins":      player["coins"],
                "bucket":     player["bucket"],
                "bucket_cap": player["bucket_cap"],
            },
            "nodes":   [self._node_wire(n) for n in self.nodes.values()] +
                       [self._node_wire(n) for n in self.structures.values()],
            "parcels": [self._parcel_wire(p) for p in self.parcels.values()],
            "market":  {"x": MARKET_TILE[0], "y": MARKET_TILE[1]},
            "prices":  self.prices,
            "world":   {"w": WORLD_W, "h": WORLD_H},
        }


engine = GameEngine()
