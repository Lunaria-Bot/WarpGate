# cogs/inventory.py
import discord
from discord.ext import commands
from db import pool

class InventoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory")
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        async with pool().acquire() as conn:
            rows = await conn.fetch("""
                SELECT uc.card_id, c.name, c.rarity, uc.qty
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id=$1
                ORDER BY c.rarity DESC, c.name ASC
            """, target.id)
            if not rows:
                await ctx.send("Inventaire vide.")
                return
            lines = [f"{r['name']} [{r['rarity']}] x{r['qty']}" for r in rows]
            await ctx.send("Inventaire:\n" + "\n".join(lines))

async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
