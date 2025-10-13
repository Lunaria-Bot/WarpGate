# cogs/faction.py
import discord
from discord.ext import commands
from db import pool

class FactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="faction")
    async def faction(self, ctx: commands.Context, faction_id: str = None):
        async with pool().acquire() as conn:
            if faction_id:
                fa = await conn.fetchrow("SELECT * FROM factions WHERE faction_id=$1", faction_id.upper())
                if not fa:
                    await ctx.send("Faction inconnue.")
                    return
                members = await conn.fetch("SELECT username FROM users WHERE faction_id=$1", faction_id.upper())
                member_list = ", ".join(m["username"] for m in members) or "Aucun membre"
                await ctx.send(f"Faction {fa['name']} ({fa['faction_id']}): {member_list}")
            else:
                u = await conn.fetchrow("SELECT faction_id FROM users WHERE user_id=$1", ctx.author.id)
                if not u or not u["faction_id"]:
                    await ctx.send("Tu n'as pas encore choisi de faction. Utilise !register.")
                    return
                fa = await conn.fetchrow("SELECT * FROM factions WHERE faction_id=$1", u["faction_id"])
                members = await conn.fetch("SELECT username FROM users WHERE faction_id=$1", u["faction_id"])
                member_list = ", ".join(m["username"] for m in members) or "Aucun membre"
                await ctx.send(f"Ta faction: {fa['name']} ({fa['faction_id']})\nMembres: {member_list}")

async def setup(bot):
    await bot.add_cog(FactionCog(bot))
