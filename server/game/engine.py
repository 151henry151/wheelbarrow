"""
In-memory game state. All mutation happens here; the DB is used for
persistence (load on startup, periodic saves, save on disconnect).
"""
import asyncio
import time
import uuid
from typing import Any

from fastapi import WebSocket

from server.game.constants import WORLD_W, WORLD_H, COLLECTION_RADIUS, COLLECTION_RATE, MARKET_TILE
from server.db import queries

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bucket_total(bucket: dict) -> float:
    return sum(bucket.values())

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class GameEngine:
    def __init__(self):
        self.players: dict[int, dict] = {}          # player_id -> player state
        self.sockets: dict[int, WebSocket] = {}     # player_id -> websocket
        self.tokens: dict[str, int] = {}            # token -> player_id
        self.nodes: dict[int, dict] = {}            # node_id -> node state
        self.prices: dict[str, float] = {}
        self._last_resource_tick = time.monotonic()
        self._last_persist = time.monotonic()

    # -- Setup --

    async def load(self):
        nodes = await queries.load_all_nodes()
        for node in nodes:
            self.nodes[node["id"]] = dict(node)
        self.prices = await queries.get_market_prices()

    # -- Sessions --

    def create_session(self, player: dict) -> str:
        token = str(uuid.uuid4())
        self.tokens[token] = player["id"]
        self.players[player["id"]] = player
        return token

    def get_player_by_token(self, token: str) -> dict | None:
        pid = self.tokens.get(token)
        return self.players.get(pid) if pid is not None else None

    def add_socket(self, player_id: int, ws: WebSocket):
        self.sockets[player_id] = ws

    async def remove_player(self, player_id: int):
        self.sockets.pop(player_id, None)
        player = self.players.get(player_id)
        if player:
            await queries.save_player(player)
        # keep player state in memory if they reconnect quickly; token stays valid

    # -- Input --

    async def handle_input(self, player_id: int, msg: dict):
        if msg.get("type") == "move":
            self._move_player(player_id, msg.get("dir"))
        elif msg.get("type") == "sell":
            await self._sell(player_id)

    def _move_player(self, player_id: int, direction: str):
        player = self.players.get(player_id)
        if not player:
            return
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(direction, (0, 0))
        nx, ny = player["x"] + dx, player["y"] + dy
        if 0 <= nx < WORLD_W and 0 <= ny < WORLD_H:
            player["x"] = nx
            player["y"] = ny

    async def _sell(self, player_id: int):
        player = self.players.get(player_id)
        if not player:
            return
        if (player["x"], player["y"]) != MARKET_TILE:
            return
        bucket = player.get("bucket", {})
        if not bucket:
            return
        earned = sum(
            int(amount) * self.prices.get(rtype, 0)
            for rtype, amount in bucket.items()
        )
        player["coins"] += int(earned)
        player["bucket"] = {}
        ws = self.sockets.get(player_id)
        if ws:
            await ws.send_json({"type": "sold", "earned": int(earned), "coins": player["coins"]})

    # -- Tick --

    async def tick(self, resource_tick_s: int, persist_interval_s: int):
        now = time.monotonic()

        # Resource tick: proximity collection
        if now - self._last_resource_tick >= resource_tick_s:
            elapsed = now - self._last_resource_tick
            self._last_resource_tick = now
            await self._do_resource_tick(elapsed)

        # Broadcast positions to all connected players
        await self._broadcast_state()

        # Periodic DB persist
        if now - self._last_persist >= persist_interval_s:
            self._last_persist = now
            for player in self.players.values():
                if player["id"] in self.sockets:
                    await queries.save_player(player)
            for node in self.nodes.values():
                await queries.save_node(node)

    async def _do_resource_tick(self, elapsed: float):
        for node in self.nodes.values():
            # Replenish node
            node["current_amount"] = min(
                node["max_amount"],
                node["current_amount"] + node["replenish_rate"] * elapsed,
            )
            # Collect into adjacent players
            for player in self.players.values():
                if player["id"] not in self.sockets:
                    continue
                if abs(player["x"] - node["x"]) <= COLLECTION_RADIUS and \
                   abs(player["y"] - node["y"]) <= COLLECTION_RADIUS:
                    cap = player["bucket_cap"]
                    current_load = _bucket_total(player["bucket"])
                    space = cap - current_load
                    if space <= 0 or node["current_amount"] <= 0:
                        continue
                    collected = min(COLLECTION_RATE, space, node["current_amount"])
                    node["current_amount"] = max(0, node["current_amount"] - collected)
                    rtype = node["node_type"]
                    player["bucket"][rtype] = round(player["bucket"].get(rtype, 0) + collected, 2)

    async def _broadcast_state(self):
        if not self.sockets:
            return
        all_players = [
            {"id": p["id"], "username": p["username"], "x": p["x"], "y": p["y"]}
            for p in self.players.values()
            if p["id"] in self.sockets
        ]
        for pid, ws in list(self.sockets.items()):
            player = self.players.get(pid)
            if not player:
                continue
            try:
                await ws.send_json({
                    "type": "tick",
                    "players": all_players,
                    "player": {
                        "id": player["id"],
                        "x": player["x"],
                        "y": player["y"],
                        "coins": player["coins"],
                        "bucket": player["bucket"],
                        "bucket_cap": player["bucket_cap"],
                    },
                    "nodes": [
                        {"id": n["id"], "x": n["x"], "y": n["y"],
                         "type": n["node_type"], "amount": round(n["current_amount"], 1)}
                        for n in self.nodes.values()
                    ],
                })
            except Exception:
                pass

    def full_state(self, player_id: int) -> dict:
        from server.game.constants import MARKET_TILE
        player = self.players[player_id]
        return {
            "type": "init",
            "player": {
                "id": player["id"],
                "username": player["username"],
                "x": player["x"],
                "y": player["y"],
                "coins": player["coins"],
                "bucket": player["bucket"],
                "bucket_cap": player["bucket_cap"],
            },
            "nodes": [
                {"id": n["id"], "x": n["x"], "y": n["y"],
                 "type": n["node_type"], "amount": round(n["current_amount"], 1),
                 "max": n["max_amount"]}
                for n in self.nodes.values()
            ],
            "market": {"x": MARKET_TILE[0], "y": MARKET_TILE[1]},
            "prices": self.prices,
            "world": {"w": WORLD_W, "h": WORLD_H},
        }


engine = GameEngine()
