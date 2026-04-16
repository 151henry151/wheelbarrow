#!/usr/bin/env python3
"""
Replace all poor_soil_tiles using the current patchy algorithm (parcel Gaussian blobs).

Run on the server after upgrading (with MariaDB reachable), then restart the app
so in-memory poor_soil reloads from the database.

  cd /home/henry/wheelbarrow
  docker compose run --rm app python scripts/regenerate_poor_soil.py
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
from server.game.terrain_features import generate_poor_soil_for_parcels

# Fixed seed so this migration is reproducible if re-run on the same parcel set.
MIGRATION_RNG_SEED = 20260417


async def main() -> None:
    await queries.get_pool()
    parcels = await queries.load_all_parcels()
    await queries.clear_all_poor_soil_tiles()
    rng = random.Random(MIGRATION_RNG_SEED)
    poor = generate_poor_soil_for_parcels(rng, parcels)
    await queries.insert_poor_soil_bulk(poor)
    await close_pool()
    print(f"[regenerate_poor_soil] {len(poor)} tiles for {len(parcels)} parcels (seed={MIGRATION_RNG_SEED}).")


if __name__ == "__main__":
    asyncio.run(main())
