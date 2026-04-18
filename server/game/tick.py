import asyncio
import logging

from server.config import settings
from server.game.engine import engine

logger = logging.getLogger("uvicorn.error")


async def run_game_loop():
    logger.info("wheelbarrow: game loop task started")
    while True:
        await asyncio.sleep(settings.game_tick_ms / 1000)
        try:
            await engine.tick(settings.resource_tick_s, settings.persist_interval_s)
        except Exception:
            logger.exception("wheelbarrow: game tick failed")
