import json
import bcrypt
import aiomysql
from server.db.connection import get_pool

# ---------------------------------------------------------------------------
# Auth / Players
# ---------------------------------------------------------------------------

async def login_or_register(username: str, password: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM players WHERE username = %s", (username,))
            row = await cur.fetchone()

            if row is None:
                pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                await cur.execute(
                    "INSERT INTO players (username, password_hash) VALUES (%s, %s)",
                    (username, pw_hash),
                )
                await cur.execute("SELECT * FROM players WHERE username = %s", (username,))
                row = await cur.fetchone()
            else:
                if row["password_hash"] is None:
                    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                    await cur.execute(
                        "UPDATE players SET password_hash=%s WHERE id=%s",
                        (pw_hash, row["id"]),
                    )
                elif not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                    return None

            row["bucket"] = json.loads(row["bucket"]) if isinstance(row["bucket"], str) else (row["bucket"] or {})
            row["pocket"] = json.loads(row["pocket"]) if isinstance(row["pocket"], str) else (row["pocket"] or {})
            return row


async def save_player(player: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE players
                   SET coins=%s, x=%s, y=%s, bucket=%s, bucket_cap=%s, pocket=%s,
                       wb_paint=%s, wb_tire=%s, wb_handle=%s, flat_tire=%s,
                       wb_bucket_level=%s, wb_tire_level=%s, wb_handle_level=%s, wb_barrow_level=%s,
                       last_seen=NOW()
                   WHERE id=%s""",
                (
                    player["coins"], player["x"], player["y"],
                    json.dumps(player["bucket"]), player["bucket_cap"],
                    json.dumps(player.get("pocket", {})),
                    player.get("wb_paint",  100), player.get("wb_tire",  100),
                    player.get("wb_handle", 100), player.get("flat_tire", 0),
                    player.get("wb_bucket_level", 1), player.get("wb_tire_level",   1),
                    player.get("wb_handle_level", 1), player.get("wb_barrow_level", 1),
                    player["id"],
                ),
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
                "INSERT INTO land_parcels (owner_id, x, y, width, height) VALUES (%s,%s,%s,%s,%s)",
                (owner_id, parcel_x, parcel_y, 10, 10),
            )
            pid = cur.lastrowid
            await cur.execute(
                """SELECT lp.*, p.username AS owner_name
                   FROM land_parcels lp JOIN players p ON lp.owner_id = p.id
                   WHERE lp.id = %s""",
                (pid,),
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
            rows = await cur.fetchall()
            for r in rows:
                r["inventory"] = json.loads(r["inventory"]) if isinstance(r["inventory"], str) else (r["inventory"] or {})
                r["config"]    = json.loads(r["config"])    if isinstance(r["config"],    str) else (r["config"]    or {})
            return rows


async def create_structure(parcel_id: int, x: int, y: int, structure_type: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "INSERT INTO structures (parcel_id, x, y, structure_type) VALUES (%s,%s,%s,%s)",
                (parcel_id, x, y, structure_type),
            )
            sid = cur.lastrowid
            await cur.execute(
                """SELECT s.*, lp.owner_id, p.username AS owner_name
                   FROM structures s
                   JOIN land_parcels lp ON s.parcel_id = lp.id
                   JOIN players p ON lp.owner_id = p.id
                   WHERE s.id = %s""",
                (sid,),
            )
            row = await cur.fetchone()
            row["inventory"] = {}
            row["config"]    = {}
            return row


async def save_structure(struct: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE structures SET inventory=%s, config=%s, last_tick=NOW() WHERE id=%s",
                (json.dumps(struct.get("inventory", {})), json.dumps(struct.get("config", {})), struct["id"]),
            )

# ---------------------------------------------------------------------------
# Resource piles
# ---------------------------------------------------------------------------

async def load_all_piles() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM resource_piles")
            return await cur.fetchall()


async def upsert_pile(parcel_id: int, owner_id: int, x: int, y: int,
                      resource_type: str, amount: float, sell_price) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """INSERT INTO resource_piles (parcel_id, owner_id, x, y, resource_type, amount, sell_price)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE amount=VALUES(amount), sell_price=VALUES(sell_price)""",
                (parcel_id, owner_id, x, y, resource_type, amount, sell_price),
            )
            await cur.execute(
                "SELECT * FROM resource_piles WHERE x=%s AND y=%s AND resource_type=%s",
                (x, y, resource_type),
            )
            return await cur.fetchone()


async def delete_pile(x: int, y: int, resource_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM resource_piles WHERE x=%s AND y=%s AND resource_type=%s",
                (x, y, resource_type),
            )

# ---------------------------------------------------------------------------
# Crops
# ---------------------------------------------------------------------------

async def load_all_crops() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM crops WHERE harvested=0")
            return await cur.fetchall()


async def create_crop(parcel_id: int, owner_id: int, x: int, y: int,
                      crop_type: str, ready_at_dt) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """INSERT INTO crops (parcel_id, owner_id, x, y, crop_type, ready_at)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (parcel_id, owner_id, x, y, crop_type, ready_at_dt),
            )
            cid = cur.lastrowid
            await cur.execute("SELECT * FROM crops WHERE id=%s", (cid,))
            return await cur.fetchone()


async def fertilize_crop(crop_id: int, new_ready_at_dt):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE crops SET fertilized_at=NOW(), ready_at=%s WHERE id=%s",
                (new_ready_at_dt, crop_id),
            )


async def harvest_crop(crop_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE crops SET harvested=1 WHERE id=%s", (crop_id,))

# ---------------------------------------------------------------------------
# Season
# ---------------------------------------------------------------------------

async def load_season_state() -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM season_state WHERE id=1")
            return await cur.fetchone()


async def save_season_state(season: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE season_state SET season=%s, season_start=NOW() WHERE id=1",
                (season,),
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
