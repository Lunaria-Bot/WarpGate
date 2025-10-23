import asyncio
import discord
import logging
from discord.ext import commands
from config import settings
from db import init_db
from redis_client import init_redis

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="w", intents=intents)

    async def setup_hook(self):
        self.db = await init_db()
        self.redis = await init_redis()

        extensions = [
            "cogs.register",
            "cogs.daily",
            "cogs.inventory",
            "cogs.warp",
            "cogs.profile",
            "cogs.admin",
            "cogs.wlogs",
            "cogs.gacha"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                logging.info(f"🔹 Cog loaded: {ext}")
            except Exception as e:
                logging.error(f"❌ Error loading {ext}: {e}")

        guild = discord.Object(id=1399784437440319508)
        try:
            synced = await self.tree.sync(guild=guild)
            logging.info(f"✅ Synced {len(synced)} slash command(s) to guild {guild.id}")
        except Exception as e:
            logging.error(f"❌ Error syncing commands: {e}")

    async def on_ready(self):
        logging.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        logging.info("📜 Available prefix commands:")
        for cmd in self.commands:
            logging.info(f" - w{cmd.name}")
        logging.info("Bot is ready!")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        await ctx.send(f"⚠️ Error: {error}")

async def main():
    bot = MyBot()
    await bot.start(settings.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
