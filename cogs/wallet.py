# cogs/wallet.py
import discord
from discord.ext import commands
from db import pool

class WalletCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wallet")
    async def wallet(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        async with pool().acquire() as conn:
            c = await conn.fetchrow("SELECT blood_coins, noble_coins FROM currencies WHERE user_id=$1", target.id)
            if not c:
                await ctx.send("Utilisateur non enregistré. Utilise !register.")
                return
            await ctx.send(f"Wallet de {target.display_name}: Blood {c['blood_coins']} | Noble {c['noble_coins']}")

async def setup(bot):
    await bot.add_cog(WalletCog(bot))
