# redis_client.py
import redis.asyncio as redis
from config import settings

_redis_client = None

async def init_redis():
    """
    Initialise le client Redis et le retourne.
    """
    global _redis_client
    _redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    return _redis_client   # <-- on retourne le client pour l’attacher à bot.redis

def client():
    """
    Retourne le client Redis global (fallback si besoin).
    """
    return _redis_client
