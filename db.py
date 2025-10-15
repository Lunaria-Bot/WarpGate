# db.py
import asyncpg
from contextlib import asynccontextmanager
from config import settings

_pool = None

async def init_db():
    """
    Initialise le pool PostgreSQL et le retourne.
    """
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=1,
        max_size=10
    )
    return _pool   # <-- on retourne le pool pour l’attacher à bot.db

def pool():
    """
    Retourne le pool global (fallback si besoin).
    """
    return _pool

@asynccontextmanager
async def tx():
    """
    Contexte transactionnel pratique :
    with await tx() as conn:
        await conn.execute(...)
    """
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
