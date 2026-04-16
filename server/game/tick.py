import asyncio
from server.config import settings
from server.game.engine import engine

async def run_game_loop():
    while True:
        await asyncio.sleep(settings.game_tick_ms / 1000)
        await engine.tick(settings.resource_tick_s, settings.persist_interval_s)
