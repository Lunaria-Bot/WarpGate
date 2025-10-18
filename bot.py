import asyncio
import discord
from discord.ext import commands
from config import settings
from db import init_db
from redis_client import init_redis

intents = discord.Intents.default()
intents.message_content = True   # indispensable pour les commandes prefix
intents.members = True           # utile pour factions/profils

bot = commands.Bot(command_prefix=settings.BOT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    print("📜 Commandes prefix disponibles :")
    for cmd in bot.commands:
        print(f" - {settings.BOT_PREFIX}{cmd.name}")
    print("Bot prêt à l’action !")

    # --- Slash command sync ---
    guild = discord.Object(id=1399784437440319508)
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} slash command(s) to guild {guild.id}")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

@bot.event
async def on_command_error(ctx, error):
    # Affiche l’erreur dans Discord pour debug
    await ctx.send(f"⚠️ Erreur: {error}")

async def main():
    # Initialisation DB et Redis
    bot.db = await init_db()          # <--- on attache le pool PostgreSQL au bot
    bot.redis = await init_redis()    # <--- idem pour Redis si tu veux y accéder dans tes cogs

    # Liste des cogs à charger
    extensions = [
        "cogs.register",
        "cogs.draw",
        "cogs.profile",
        "cogs.wallet",
        "cogs.inventory",
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
            await bot.load_extension(ext)
            print(f"🔹 Cog chargé: {ext}")
        except Exception as e:
            print(f"❌ Erreur chargement {ext}: {e}")

    await bot.start(settings.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
