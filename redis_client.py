# redis_client.py
import redis.asyncio as redis
from config import settings

redis_client = None

async def init_redis():
    global redis_client
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
