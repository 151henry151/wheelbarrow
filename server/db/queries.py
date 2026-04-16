import json
import aiomysql
from passlib.context import CryptContext
from server.db.connection import get_pool

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Auth / Players
# ---------------------------------------------------------------------------

async def login_or_register(username: str, password: str) -> dict | None:
    """
    Create a new account or verify an existing one.
    Returns the player dict on success, None on bad password.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM players WHERE username = %s", (username,))
            row = await cur.fetchone()

            if row is None:
                # New player
                pw_hash = _pwd.hash(password)
                await cur.execute(
                    "INSERT INTO players (username, password_hash) VALUES (%s, %s)",
                    (username, pw_hash),
                )
                await cur.execute("SELECT * FROM players WHERE username = %s", (username,))
                row = await cur.fetchone()
            else:
                if row["password_hash"] is None:
                    # Legacy account (no password yet) — adopt this password
                    pw_hash = _pwd.hash(password)
                    await cur.execute(
                        "UPDATE players SET password_hash=%s WHERE id=%s",
                        (pw_hash, row["id"]),
                    )
                elif not _pwd.verify(password, row["password_hash"]):
                    return None

            row["bucket"] = json.loads(row["bucket"]) if isinstance(row["bucket"], str) else (row["bucket"] or {})
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
# Land parcels
# ---------------------------------------------------------------------------

async def load_all_parcels() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT lp.*, p.username AS owner_name
                   FROM land_parcels lp
                   JOIN players p ON lp.owner_id = p.id"""
            )
            return await cur.fetchall()

async def create_parcel(owner_id: int, parcel_x: int, parcel_y: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """INSERT INTO land_parcels (owner_id, x, y, width, height)
                   VALUES (%s, %s, %s, %s, %s)""",
                (owner_id, parcel_x, parcel_y, 10, 10),
            )
            parcel_id = cur.lastrowid
            await cur.execute(
                """SELECT lp.*, p.username AS owner_name
                   FROM land_parcels lp JOIN players p ON lp.owner_id = p.id
                   WHERE lp.id = %s""",
                (parcel_id,),
            )
            return await cur.fetchone()

# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

async def load_all_structures() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT s.*, lp.owner_id, p.username AS owner_name
                   FROM structures s
                   JOIN land_parcels lp ON s.parcel_id = lp.id
                   JOIN players p ON lp.owner_id = p.id"""
            )
            return await cur.fetchall()

async def create_structure(parcel_id: int, x: int, y: int, structure_type: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "INSERT INTO structures (parcel_id, x, y, structure_type) VALUES (%s,%s,%s,%s)",
                (parcel_id, x, y, structure_type),
            )
            struct_id = cur.lastrowid
            await cur.execute(
                """SELECT s.*, lp.owner_id, p.username AS owner_name
                   FROM structures s
                   JOIN land_parcels lp ON s.parcel_id = lp.id
                   JOIN players p ON lp.owner_id = p.id
                   WHERE s.id = %s""",
                (struct_id,),
            )
            return await cur.fetchone()

async def save_structure(struct: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE structures SET last_tick=NOW() WHERE id=%s",
                (struct["id"],),
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

async def update_market_prices(prices: dict[str, float]):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for rtype, price in prices.items():
                await cur.execute(
                    "UPDATE market_prices SET price_per_unit=%s, last_updated=NOW() WHERE resource_type=%s",
                    (price, rtype),
                )
