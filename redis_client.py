# redis_client.py
import aioredis
from config import settings

redis = None

async def init_redis():
    global redis
    redis = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
