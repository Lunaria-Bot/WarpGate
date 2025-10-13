# config.py
from pydantic_settings import BaseSettings  # ✅ nouveau import

class Settings(BaseSettings):
    DISCORD_TOKEN: str
    PG_DSN: str
    REDIS_URL: str
    BOT_PREFIX: str = "!"
    DRAW_COOLDOWN_SEC: int = 600  # 10 minutes

    class Config:
        env_file = ".env"

settings = Settings()
