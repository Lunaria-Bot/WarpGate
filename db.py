# db.py
import asyncpg
from contextlib import asynccontextmanager
from config import settings

_pool = None

async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(dsn=settings.PG_DSN, min_size=1, max_size=10)

def pool():
    return _pool

@asynccontextmanager
async def tx():
    conn = await _pool.acquire()
    tr = conn.transaction()
    try:
        await tr.start()
        yield conn
        await tr.commit()
    except:
        await tr.rollback()
        raise
    finally:
        await _pool.release(conn)
