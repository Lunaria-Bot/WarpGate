from contextlib import asynccontextmanager

@asynccontextmanager
async def db_transaction(pool):
    """
    Usage:
    async with db_transaction(bot.db) as conn:
        await conn.execute(...)
    """
    conn = await pool.acquire()
    try:
        async with conn.transaction():
            yield conn
    finally:
        await pool.release(conn)
