# cogs/trade.py
import discord
from discord.ext import commands
from db import tx
from redis_client import redis_client

class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.trade_sessions = {}  # channel_id -> trade_id

    @commands.command(name="trade")
    async def trade(self, ctx: commands.Context, action: str = None, target: discord.Member = None):
        # Ici tu peux reprendre la logique complète de ton trade (open, add, confirm, cancel)
        # en utilisant redis_client si tu veux stocker des états temporaires
        await ctx.send("Squelette de trade prêt. Implémente la logique complète ici.")

async def setup(bot):
    await bot.add_cog(TradeCog(bot))
