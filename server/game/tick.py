import asyncio
import logging
import time

from server.config import settings
from server.game.engine import engine

logger = logging.getLogger("uvicorn.error")


async def run_game_loop():
    logger.info("wheelbarrow: game loop task started")
    while True:
        await asyncio.sleep(settings.game_tick_ms / 1000)
        t0 = time.monotonic()
        try:
            await engine.tick(settings.resource_tick_s, settings.persist_interval_s)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("wheelbarrow: game tick failed")
        else:
            dt = time.monotonic() - t0
            if dt > 0.2:
                logger.warning("wheelbarrow: slow tick %.3fs (event loop may stall WebSocket)", dt)
