import json
import aiomysql
from server.db.connection import get_pool

# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

async def get_or_create_player(username: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM players WHERE username = %s", (username,))
            row = await cur.fetchone()
            if row:
                row["bucket"] = json.loads(row["bucket"]) if isinstance(row["bucket"], str) else row["bucket"]
                return row
            await cur.execute(
                "INSERT INTO players (username) VALUES (%s)", (username,)
            )
            await cur.execute("SELECT * FROM players WHERE username = %s", (username,))
            row = await cur.fetchone()
            row["bucket"] = {}
            return row

async def save_player(player: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE players
                   SET coins=%s, x=%s, y=%s, bucket=%s, bucket_cap=%s, last_seen=NOW()
                   WHERE id=%s""",
                (player["coins"], player["x"], player["y"],
                 json.dumps(player["bucket"]), player["bucket_cap"], player["id"]),
            )

# ---------------------------------------------------------------------------
# Resource nodes
# ---------------------------------------------------------------------------

async def load_all_nodes() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM resource_nodes")
            return await cur.fetchall()

async def save_node(node: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE resource_nodes SET current_amount=%s, last_tick=NOW() WHERE id=%s",
                (node["current_amount"], node["id"]),
            )

# ---------------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------------

async def get_market_prices() -> dict[str, float]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT resource_type, price_per_unit FROM market_prices")
            rows = await cur.fetchall()
            return {r["resource_type"]: r["price_per_unit"] for r in rows}
