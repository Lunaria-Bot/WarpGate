# cogs/admin.py
import discord
from discord.ext import commands
from db import pool

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="initdb")
    @commands.is_owner()
    async def initdb(self, ctx):
        async with pool().acquire() as conn:
            sql = open("sql/00_init.sql").read()
            await conn.execute(sql)
        await ctx.send("✅ Base initialisée.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
