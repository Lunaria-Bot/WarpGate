import asyncio
import discord
from discord.ext import commands
from config import settings
from db import init_db
from redis_client import init_redis

intents = discord.Intents.default()
intents.message_content = True   # indispensable pour les commandes prefix
intents.members = True           # utile pour factions/profils

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=settings.BOT_PREFIX, intents=intents)

    async def setup_hook(self):
        # Attach DB and Redis before loading cogs
        self.db = await init_db()
        self.redis = await init_redis()

        # Liste des cogs à charger
        extensions = [
            "cogs.register",
            "cogs.draw",
            "cogs.profile",
            "cogs.wallet",
            "cogs.cards",
            "cogs.announcement",
            "cogs.trade",
            "cogs.admin",
            "cogs.upgrade",
            "cogs.cooldown_reset",
            "cogs.daily",
            "cogs.quests",
            "cogs.butcher",
            "cogs.buddy"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"🔹 Cog chargé: {ext}")
            except Exception as e:
                print(f"❌ Erreur chargement {ext}: {e}")

        # --- Slash command sync ---
        guild = discord.Object(id=1399784437440319508)  # ton serveur
        try:
            synced = await self.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} slash command(s) to guild {guild.id}")
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")

    async def on_ready(self):
        print(f"✅ Connecté en tant que {self.user} (ID: {self.user.id})")
        print("📜 Commandes prefix disponibles :")
        for cmd in self.commands:
            print(f" - {settings.BOT_PREFIX}{cmd.name}")
        print("Bot prêt à l’action !")

    async def on_command_error(self, ctx, error):
        # Ignore CommandNotFound to avoid spam
        if isinstance(error, commands.CommandNotFound):
            return
        await ctx.send(f"⚠️ Erreur: {error}")


async def main():
    bot = MyBot()
    await bot.start(settings.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
