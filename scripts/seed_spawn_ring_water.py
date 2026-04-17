#!/usr/bin/env python3
"""
Add ponds in a ring just outside the spawn dry zone (for worlds generated with a large
spawn exclusion, where the nearest natural water can be very far from PLAYER_SPAWN).

Idempotent: INSERT IGNORE; safe to re-run.

  cd /home/henry/wheelbarrow
  docker compose run --rm app python scripts/seed_spawn_ring_water.py
  # then restart the game process so in-memory water_tiles reloads:
  sudo systemctl restart wheelbarrow
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
from server.game.terrain_features import extra_ponds_outside_spawn_ring

MIGRATION_RNG_SEED = 991_011


async def main() -> None:
    await queries.get_pool()
    existing = set(await queries.load_all_water_tiles())
    nodes = await queries.load_all_nodes()
    node_pos = {(int(n["x"]), int(n["y"])) for n in nodes}
    towns = [dict(t) for t in await queries.load_all_towns()]
    rng = random.Random(MIGRATION_RNG_SEED)
    extra = extra_ponds_outside_spawn_ring(rng, existing, node_pos, towns)
    await queries.insert_water_tiles_bulk(extra)
    await close_pool()
    print(
        f"[seed_spawn_ring_water] inserted up to {len(extra)} new tiles "
        f"(seed={MIGRATION_RNG_SEED}, existing was {len(existing)}).",
    )


if __name__ == "__main__":
    asyncio.run(main())
