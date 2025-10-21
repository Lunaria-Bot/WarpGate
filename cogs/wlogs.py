import discord
from discord.ext import commands

class WLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wlogs")
    async def fake_log(self, ctx, *, username: str):
        print(f'LOGS : "{username}" has draw')
        await ctx.send(f"📝 Logged draw for **{username}**.")

async def setup(bot):
    await bot.add_cog(WLogs(bot))
