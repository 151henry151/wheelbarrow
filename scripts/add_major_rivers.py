#!/usr/bin/env python3
"""
Add long multi-town rivers (4–8 tiles wide) to an existing world.

Idempotent: INSERT IGNORE; safe to re-run. Skips tiles that are resource nodes,
bridge sites, or NPC shop footprints.

  cd /home/henry/wheelbarrow
  docker compose run --rm app python scripts/add_major_rivers.py
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
from server.game.terrain_features import generate_major_rivers

# Distinct from world_gen (42) and engine empty-water seed (991) so migration
# matches a dedicated rollout; deterministic across runs.
MIGRATION_RNG_SEED = 993_017


async def main() -> None:
    await queries.get_pool()
    nodes = await queries.load_all_nodes()
    node_pos = {(int(n["x"]), int(n["y"])) for n in nodes}
    bridges = set(await queries.load_all_bridge_tiles())
    towns = [dict(t) for t in await queries.load_all_towns()]
    rng = random.Random(MIGRATION_RNG_SEED)
    extra = generate_major_rivers(rng, node_pos, towns, extra_blocked=bridges)
    before = await queries.count_water_tiles()
    await queries.insert_water_tiles_bulk(extra)
    after = await queries.count_water_tiles()
    await close_pool()
    print(
        f"[add_major_rivers] inserted up to {len(extra)} river tiles "
        f"(seed={MIGRATION_RNG_SEED}; water {before} -> {after}).",
    )


if __name__ == "__main__":
    asyncio.run(main())
