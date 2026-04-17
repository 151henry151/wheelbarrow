#!/usr/bin/env python3
"""
Insert additional wild resource nodes using current world_gen density rules.

Use once after upgrading when the live DB was generated with older, sparser settings.
Skips tiles that already have a resource node.

  docker compose run --rm app python scripts/densify_resource_nodes.py
"""
from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from server.db import queries
from server.db.connection import close_pool
from server.game.world_gen import densify_nodes_for_existing_world

MIGRATION_RNG_SEED = 20260419


async def main() -> None:
    await queries.get_pool()
    rows = await queries.load_all_nodes()
    occupied = {(int(n["x"]), int(n["y"])) for n in rows}
    rng = random.Random(MIGRATION_RNG_SEED)
    new_nodes = densify_nodes_for_existing_world(rng, occupied)
    await queries.insert_nodes_bulk(new_nodes)
    await close_pool()
    print(
        f"[densify_resource_nodes] inserted {len(new_nodes)} nodes "
        f"(existing {len(occupied)} tiles skipped; seed={MIGRATION_RNG_SEED}).",
    )


if __name__ == "__main__":
    asyncio.run(main())
