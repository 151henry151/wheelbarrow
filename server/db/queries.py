import json
import bcrypt
import aiomysql
from server.db.connection import get_pool

# ---------------------------------------------------------------------------
# Auth / Players
# ---------------------------------------------------------------------------

async def ensure_player_movement_columns():
    """v0.11.0: float x/y + angle for continuous movement (idempotent)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'players' AND COLUMN_NAME = 'angle'",
            )
            if not await cur.fetchone():
                await cur.execute(
                    "ALTER TABLE players ADD COLUMN angle DOUBLE NOT NULL DEFAULT 1.5707963267948966",
                )
            await cur.execute(
                "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'players' AND COLUMN_NAME = 'x'",
            )
            row = await cur.fetchone()
            if row and row[0] and str(row[0]).lower() in (
                "int", "mediumint", "bigint", "smallint", "tinyint",
            ):
                await cur.execute("ALTER TABLE players MODIFY COLUMN x DOUBLE NOT NULL DEFAULT 500")
                await cur.execute("ALTER TABLE players MODIFY COLUMN y DOUBLE NOT NULL DEFAULT 500")


async def login_or_register(username: str, password: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM players WHERE username=%s", (username,))
            row = await cur.fetchone()
            if row is None:
                pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                await cur.execute(
                    "INSERT INTO players (username, password_hash, x, y) VALUES (%s,%s,%s,%s)",
                    (username, pw_hash, 500, 500),
                )
                await cur.execute("SELECT * FROM players WHERE username=%s", (username,))
                row = await cur.fetchone()
            else:
                if row["password_hash"] is None:
                    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                    await cur.execute("UPDATE players SET password_hash=%s WHERE id=%s", (pw_hash, row["id"]))
                elif not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                    return None
            row["bucket"] = json.loads(row["bucket"]) if isinstance(row["bucket"], str) else (row["bucket"] or {})
            row["pocket"] = json.loads(row["pocket"]) if isinstance(row["pocket"], str) else (row["pocket"] or {})
            row["x"] = float(row["x"])
            row["y"] = float(row["y"])
            row["angle"] = float(row["angle"]) if row.get("angle") is not None else 1.5707963267948966
            return row


async def save_player(player: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE players
                   SET coins=%s, x=%s, y=%s, angle=%s, bucket=%s, bucket_cap=%s, pocket=%s,
                       wb_paint=%s, wb_tire=%s, wb_handle=%s, wb_barrow=%s, flat_tire=%s,
                       wb_bucket_level=%s, wb_tire_level=%s, wb_handle_level=%s, wb_barrow_level=%s,
                       last_seen=NOW()
                   WHERE id=%s""",
                (player["coins"], player["x"], player["y"], player.get("angle", 1.5707963267948966),
                 json.dumps(player.get("bucket", {})), player["bucket_cap"],
                 json.dumps(player.get("pocket", {})),
                 player.get("wb_paint", 100), player.get("wb_tire", 100),
                 player.get("wb_handle", 100), player.get("wb_barrow", 100),
                 player.get("flat_tire", 0),
                 player.get("wb_bucket_level", 1), player.get("wb_tire_level", 1),
                 player.get("wb_handle_level", 1), player.get("wb_barrow_level", 1),
                 player["id"]),
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


async def insert_nodes_bulk(nodes: list[dict]):
    if not nodes:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO resource_nodes (x,y,node_type,current_amount,max_amount,replenish_rate,tree_variant) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [
                    (
                        n["x"],
                        n["y"],
                        n["node_type"],
                        n["current_amount"],
                        n["max_amount"],
                        n["replenish_rate"],
                        int(n.get("tree_variant", 0) or 0),
                    )
                    for n in nodes
                ],
            )


async def ensure_resource_nodes_tree_variant():
    """Add tree_variant for wild wood sprite variety (init.sql only runs on fresh DB)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "ALTER TABLE resource_nodes ADD COLUMN tree_variant TINYINT UNSIGNED NOT NULL DEFAULT 0",
                )
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Towns
# ---------------------------------------------------------------------------

async def ensure_towns_npc_district_column():
    """Add npc_district to existing DB volumes (init.sql only runs on fresh DB)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "ALTER TABLE towns ADD COLUMN npc_district JSON NULL",
                )
            except Exception:
                pass


async def update_town_npc_district(town_id: int, district: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE towns SET npc_district=%s WHERE id=%s",
                (json.dumps(district), town_id),
            )


async def load_all_towns() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM towns")
            rows = await cur.fetchall()
            for r in rows:
                r["boundary"] = json.loads(r["boundary"]) if isinstance(r["boundary"], str) else (r["boundary"] or [])
                nd = r.get("npc_district")
                if isinstance(nd, str):
                    try:
                        nd = json.loads(nd)
                    except json.JSONDecodeError:
                        nd = None
                r["npc_district"] = nd
            return rows


async def insert_towns_bulk(towns: list[dict]) -> list[int]:
    """Insert towns and return list of inserted IDs in same order."""
    if not towns:
        return []
    pool = await get_pool()
    ids  = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for t in towns:
                nd = t.get("npc_district")
                await cur.execute(
                    "INSERT INTO towns (name, center_x, center_y, boundary, npc_district) VALUES (%s,%s,%s,%s,%s)",
                    (t["name"], t["center_x"], t["center_y"], json.dumps(t["boundary"]),
                     json.dumps(nd) if nd else None),
                )
                ids.append(cur.lastrowid)
    return ids


async def update_town(town: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE towns SET custom_name=%s, founder_id=%s, leader_id=%s,
                   tax_rate=%s, treasury=%s, hall_built=%s, next_election_at=%s
                   WHERE id=%s""",
                (town.get("custom_name"), town.get("founder_id"), town.get("leader_id"),
                 town.get("tax_rate", 0), town.get("treasury", 0), town.get("hall_built", 0),
                 town.get("next_election_at"), town["id"]),
            )


async def get_town_landowners(town_id: int) -> list[dict]:
    """Players who own at least one parcel in this town."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT DISTINCT p.id, p.username
                   FROM world_parcels wp
                   JOIN players p ON wp.owner_id = p.id
                   WHERE wp.town_id = %s AND wp.owner_id IS NOT NULL""",
                (town_id,),
            )
            return await cur.fetchall()

# ---------------------------------------------------------------------------
# World parcels
# ---------------------------------------------------------------------------

async def load_all_parcels() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT wp.*, t.name AS town_name,
                          COALESCE(t.custom_name, t.name) AS display_town_name
                   FROM world_parcels wp
                   LEFT JOIN towns t ON wp.town_id = t.id"""
            )
            return await cur.fetchall()


async def insert_parcels_bulk(parcels: list[dict], town_ids: list[int]):
    """Insert pre-generated parcels. town_idx references the town_ids list."""
    if not parcels:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            rows = []
            for p in parcels:
                tid = town_ids[p["town_idx"]] if p.get("town_idx") is not None else None
                rows.append((p["x"], p["y"], p["w"], p["h"], p["price"], tid))
            await cur.executemany(
                "INSERT INTO world_parcels (x,y,w,h,price,town_id) VALUES (%s,%s,%s,%s,%s,%s)",
                rows,
            )


async def buy_parcel(parcel_id: int, owner_id: int, owner_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE world_parcels SET owner_id=%s, owner_name=%s, purchased_at=NOW() WHERE id=%s AND owner_id IS NULL",
                (owner_id, owner_name, parcel_id),
            )
            return cur.rowcount > 0  # False if someone bought it first (race)

# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

async def load_all_structures() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT s.*, wp.owner_id, p.username AS owner_name
                   FROM structures s
                   JOIN world_parcels wp ON s.parcel_id = wp.id
                   JOIN players p ON wp.owner_id = p.id"""
            )
            rows = await cur.fetchall()
            for r in rows:
                r["inventory"] = json.loads(r["inventory"]) if isinstance(r["inventory"], str) else (r["inventory"] or {})
                r["config"]    = json.loads(r["config"])    if isinstance(r["config"],    str) else (r["config"]    or {})
            return rows


async def create_structure(
    parcel_id: int, x: int, y: int, structure_type: str, config: dict | None = None,
) -> dict:
    config = config or {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """INSERT INTO structures (parcel_id,x,y,structure_type,config,inventory)
                   VALUES (%s,%s,%s,%s,%s,'{}')""",
                (parcel_id, x, y, structure_type, json.dumps(config)),
            )
            sid = cur.lastrowid
            await cur.execute(
                """SELECT s.*, wp.owner_id, p.username AS owner_name
                   FROM structures s
                   JOIN world_parcels wp ON s.parcel_id = wp.id
                   JOIN players p ON wp.owner_id = p.id
                   WHERE s.id=%s""",
                (sid,),
            )
            row = await cur.fetchone()
            row["inventory"] = json.loads(row["inventory"]) if isinstance(row["inventory"], str) else (row["inventory"] or {})
            row["config"] = json.loads(row["config"]) if isinstance(row["config"], str) else (row["config"] or {})
            return row


async def save_structure(struct: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE structures SET inventory=%s, config=%s, last_tick=NOW() WHERE id=%s",
                (json.dumps(struct.get("inventory", {})), json.dumps(struct.get("config", {})), struct["id"]),
            )


async def delete_structure(struct_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM structures WHERE id=%s", (struct_id,))


async def ensure_terrain_tables():
    """Water, bridges, poor soil — init.sql only runs on fresh DB volumes."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """CREATE TABLE IF NOT EXISTS water_tiles (
                    x INT NOT NULL, y INT NOT NULL, PRIMARY KEY (x, y)
                )""",
            )
            await cur.execute(
                """CREATE TABLE IF NOT EXISTS bridge_tiles (
                    x INT NOT NULL, y INT NOT NULL, PRIMARY KEY (x, y)
                )""",
            )
            await cur.execute(
                """CREATE TABLE IF NOT EXISTS bridge_progress (
                    x INT NOT NULL, y INT NOT NULL,
                    wood_deposited FLOAT NOT NULL DEFAULT 0,
                    coins_paid TINYINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (x, y)
                )""",
            )
            await cur.execute(
                """CREATE TABLE IF NOT EXISTS poor_soil_tiles (
                    x INT NOT NULL, y INT NOT NULL, PRIMARY KEY (x, y)
                )""",
            )


async def count_water_tiles() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM water_tiles")
            (n,) = await cur.fetchone()
            return int(n or 0)


async def insert_water_tiles_bulk(tiles: set[tuple[int, int]] | list[tuple[int, int]]):
    if not tiles:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT IGNORE INTO water_tiles (x, y) VALUES (%s, %s)",
                list(tiles),
            )


async def delete_water_tile(x: int, y: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM water_tiles WHERE x=%s AND y=%s", (x, y))


async def load_all_water_tiles() -> list[tuple[int, int]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT x, y FROM water_tiles")
            return [(r[0], r[1]) for r in await cur.fetchall()]


async def insert_bridge_tile(x: int, y: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT IGNORE INTO bridge_tiles (x, y) VALUES (%s, %s)",
                (x, y),
            )


async def load_all_bridge_tiles() -> list[tuple[int, int]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT x, y FROM bridge_tiles")
            return [(r[0], r[1]) for r in await cur.fetchall()]


async def upsert_bridge_progress(x: int, y: int, wood_deposited: float, coins_paid: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO bridge_progress (x, y, wood_deposited, coins_paid)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE wood_deposited=%s, coins_paid=%s""",
                (x, y, wood_deposited, coins_paid, wood_deposited, coins_paid),
            )


async def delete_bridge_progress(x: int, y: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM bridge_progress WHERE x=%s AND y=%s", (x, y))


async def load_all_bridge_progress() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT x, y, wood_deposited, coins_paid FROM bridge_progress")
            return await cur.fetchall()


async def clear_all_poor_soil_tiles() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("TRUNCATE TABLE poor_soil_tiles")


async def insert_poor_soil_bulk(tiles: set[tuple[int, int]] | list[tuple[int, int]]):
    if not tiles:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT IGNORE INTO poor_soil_tiles (x, y) VALUES (%s, %s)",
                list(tiles),
            )


async def delete_poor_soil_tile(x: int, y: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM poor_soil_tiles WHERE x=%s AND y=%s", (x, y))


async def load_all_poor_soil_tiles() -> list[tuple[int, int]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT x, y FROM poor_soil_tiles")
            return [(r[0], r[1]) for r in await cur.fetchall()]

# ---------------------------------------------------------------------------
# Resource piles
# ---------------------------------------------------------------------------

async def load_all_piles() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM resource_piles")
            return await cur.fetchall()


async def upsert_pile(parcel_id, owner_id, x, y, resource_type, amount, sell_price) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """INSERT INTO resource_piles (parcel_id,owner_id,x,y,resource_type,amount,sell_price)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE amount=VALUES(amount), sell_price=VALUES(sell_price)""",
                (parcel_id, owner_id, x, y, resource_type, amount, sell_price),
            )
            await cur.execute(
                "SELECT * FROM resource_piles WHERE x=%s AND y=%s AND resource_type=%s",
                (x, y, resource_type),
            )
            return await cur.fetchone()


async def delete_pile(x, y, resource_type):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM resource_piles WHERE x=%s AND y=%s AND resource_type=%s",
                (x, y, resource_type),
            )


async def ensure_world_roads_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """CREATE TABLE IF NOT EXISTS world_roads (
                    x INT NOT NULL,
                    y INT NOT NULL,
                    PRIMARY KEY (x, y)
                )""",
            )


async def migrate_resource_piles_parcel_optional():
    """Allow piles off formal parcels (unload anywhere); drop parcel FK if present."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='resource_piles'
                   AND CONSTRAINT_TYPE='FOREIGN KEY'""",
            )
            for (cname,) in await cur.fetchall() or []:
                try:
                    await cur.execute(
                        f"ALTER TABLE resource_piles DROP FOREIGN KEY `{cname}`",
                    )
                except Exception:
                    pass
            try:
                await cur.execute(
                    "ALTER TABLE resource_piles MODIFY parcel_id INT NULL",
                )
            except Exception:
                pass


async def load_all_roads() -> list[tuple[int, int]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT x, y FROM world_roads")
            return [(r[0], r[1]) for r in await cur.fetchall()]


async def insert_road_bulk(tiles: list[tuple[int, int]]):
    if not tiles:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT IGNORE INTO world_roads (x, y) VALUES (%s, %s)",
                list(tiles),
            )


# ---------------------------------------------------------------------------
# Crops & soil
# ---------------------------------------------------------------------------

async def ensure_crop_winter_dead_column():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT COUNT(*) FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'crops' AND COLUMN_NAME = 'winter_dead'""",
            )
            (n,) = await cur.fetchone()
            if n == 0:
                await cur.execute(
                    "ALTER TABLE crops ADD COLUMN winter_dead TINYINT NOT NULL DEFAULT 0",
                )


async def ensure_soil_tiles_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """CREATE TABLE IF NOT EXISTS soil_tiles (
                    x INT NOT NULL,
                    y INT NOT NULL,
                    tilled TINYINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (x, y)
                )""",
            )


async def load_all_soil_tiles() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT x, y, tilled FROM soil_tiles")
            return await cur.fetchall()


async def upsert_soil_tile(x: int, y: int, tilled: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO soil_tiles (x, y, tilled) VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE tilled=VALUES(tilled)""",
                (x, y, tilled),
            )


async def load_all_crops() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM crops WHERE COALESCE(harvested, 0) = 0")
            return await cur.fetchall()


async def cleanup_legacy_harvested_crop_rows():
    """Old harvest flow set harvested=1 and kept the row, blocking UNIQUE (x,y) replants. Remove those."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM crops WHERE harvested=1")


async def create_crop(parcel_id, owner_id, x, y, crop_type, ready_at_dt) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """INSERT INTO crops (parcel_id,owner_id,x,y,crop_type,ready_at,winter_dead)
                   VALUES (%s,%s,%s,%s,%s,%s,0)""",
                (parcel_id, owner_id, x, y, crop_type, ready_at_dt),
            )
            cid = cur.lastrowid
            await cur.execute("SELECT * FROM crops WHERE id=%s", (cid,))
            return await cur.fetchone()


async def fertilize_crop(crop_id, new_ready_at_dt):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE crops SET fertilized_at=NOW(), ready_at=%s WHERE id=%s",
                (new_ready_at_dt, crop_id),
            )


async def harvest_crop(crop_id):
    """Remove the crop row so another can be planted at the same (x,y) (UNIQUE idx_crop_xy)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM crops WHERE id=%s", (crop_id,))


async def mark_all_crops_winter_dead():
    """Frost-kill standing crops; they stay on the map until tilled away."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE crops SET winter_dead=1 WHERE COALESCE(harvested,0)=0 AND COALESCE(winter_dead,0)=0",
            )


async def delete_all_active_crops():
    """Legacy: winter used to DELETE crops. Prefer mark_all_crops_winter_dead."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM crops WHERE COALESCE(harvested, 0) = 0")

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
# Market prices
# ---------------------------------------------------------------------------

async def ensure_market_price_rows(defaults: dict[str, float]):
    """Insert missing resource rows (e.g. new types on existing DB volumes)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT resource_type FROM market_prices")
            have = {r[0] for r in await cur.fetchall()}
            for rtype, price in defaults.items():
                if rtype in have:
                    continue
                await cur.execute(
                    "INSERT INTO market_prices (resource_type, price_per_unit) VALUES (%s, %s)",
                    (rtype, price),
                )


async def get_market_prices() -> dict[str, float]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT resource_type, price_per_unit FROM market_prices")
            return {r["resource_type"]: r["price_per_unit"] for r in await cur.fetchall()}


async def update_market_prices(prices: dict[str, float]):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for rtype, price in prices.items():
                await cur.execute(
                    "UPDATE market_prices SET price_per_unit=%s, last_updated=NOW() WHERE resource_type=%s",
                    (price, rtype),
                )

# ---------------------------------------------------------------------------
# Town votes
# ---------------------------------------------------------------------------

async def cast_vote(town_id: int, voter_id: int, candidate_id: int, vote_cycle: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO town_votes (town_id, voter_id, candidate_id, vote_cycle)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE candidate_id=VALUES(candidate_id)""",
                (town_id, voter_id, candidate_id, vote_cycle),
            )


async def get_vote_results(town_id: int, vote_cycle: int) -> list[dict]:
    """Returns [{candidate_id, votes}] sorted by votes desc."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT candidate_id, COUNT(*) AS votes
                   FROM town_votes WHERE town_id=%s AND vote_cycle=%s
                   GROUP BY candidate_id ORDER BY votes DESC""",
                (town_id, vote_cycle),
            )
            return await cur.fetchall()

# ---------------------------------------------------------------------------
# Town bans
# ---------------------------------------------------------------------------

async def load_town_bans() -> dict[int, dict]:
    """Returns {town_id: {"structures": set, "goods": set}}"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM town_bans")
            rows = await cur.fetchall()
    result: dict[int, dict] = {}
    for r in rows:
        tid = r["town_id"]
        if tid not in result:
            result[tid] = {"structures": set(), "goods": set()}
        if r["ban_type"] == "structure":
            result[tid]["structures"].add(r["target"])
        else:
            result[tid]["goods"].add(r["target"])
    return result


async def set_ban(town_id: int, ban_type: str, target: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT IGNORE INTO town_bans (town_id,ban_type,target) VALUES (%s,%s,%s)",
                (town_id, ban_type, target),
            )


async def remove_ban(town_id: int, ban_type: str, target: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM town_bans WHERE town_id=%s AND ban_type=%s AND target=%s",
                (town_id, ban_type, target),
            )

# ---------------------------------------------------------------------------
# World gen flag
# ---------------------------------------------------------------------------

async def world_is_generated() -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT done FROM world_gen_state WHERE id=1")
            row = await cur.fetchone()
            return bool(row and row[0])


async def mark_world_generated():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE world_gen_state SET done=1 WHERE id=1")
