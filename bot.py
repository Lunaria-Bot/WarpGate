import asyncio
import discord
from discord.ext import commands
from config import settings
from db import init_db
from redis_client import init_redis

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
            "cogs.wlogs"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"🔹 Cog loaded: {ext}")
            except Exception as e:
                print(f"❌ Error loading {ext}: {e}")

        guild = discord.Object(id=1399784437440319508)
        try:
            synced = await self.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} slash command(s) to guild {guild.id}")
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        print("📜 Available prefix commands:")
        for cmd in self.commands:
            print(f" - w{cmd.name}")
        print("Bot is ready!")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        await ctx.send(f"⚠️ Error: {error}")

async def main():
    bot = MyBot()
    await bot.start(settings.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
