#!/usr/bin/env python3
"""Print road∩water and road∩resource_nodes counts — useful when debugging movement near paths."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from server.db import queries
from server.db.connection import close_pool


async def main() -> None:
    pool = await queries.get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM world_roads r
                INNER JOIN water_tiles w ON w.x = r.x AND w.y = r.y
                """
            )
            row = await cur.fetchone()
            rw = int(row[0]) if row else 0
            await cur.execute(
                """
                SELECT COUNT(*) FROM world_roads r
                INNER JOIN resource_nodes n ON n.x = r.x AND n.y = r.y
                """
            )
            row = await cur.fetchone()
            rn = int(row[0]) if row else 0
    print(f"road ∩ water tiles: {rw}")
    print(f"road ∩ resource_nodes tiles: {rn}")
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
