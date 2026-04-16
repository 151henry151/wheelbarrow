import asyncio
import aiomysql
from server.config import settings

_pool: aiomysql.Pool | None = None

async def get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        for attempt in range(10):
            try:
                _pool = await aiomysql.create_pool(
                    host=settings.db_host,
                    port=settings.db_port,
                    db=settings.db_name,
                    user=settings.db_user,
                    password=settings.db_password,
                    autocommit=True,
                    charset="utf8mb4",
                    minsize=2,
                    maxsize=10,
                )
                return _pool
            except Exception:
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Could not connect to MariaDB after 10 attempts")
    return _pool

async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
