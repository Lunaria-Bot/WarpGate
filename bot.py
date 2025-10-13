# bot.py
import discord
from discord.ext import commands
from config import settings
from db import init_db
from redis_client import init_redis

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=settings.BOT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user} (ID: {bot.user.id})")

async def main():
    await init_db()
    await init_redis()
    for ext in [
    "cogs.register",
    "cogs.draw",
    "cogs.profile",
    "cogs.wallet",
    "cogs.inventory",
    "cogs.faction",
    "cogs.trade"
]:
    await bot.load_extension(ext)

        await bot.load_extension(ext)
    await bot.start(settings.DISCORD_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
