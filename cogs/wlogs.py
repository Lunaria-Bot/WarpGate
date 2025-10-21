import discord
from discord.ext import commands
from io import StringIO
from datetime import datetime, timedelta
import random

class WLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wlogs")
    async def fake_log_file(self, ctx, *, username: str):
        """
        Generates a fake log file for the given username and sends it as a .txt file.
        Simulates 5 days of draws with 1-hour randomized gaps.
        """
        start_date = datetime(2025, 10, 17)
        logs = []

        for day in range(5):
            base_time = start_date + timedelta(days=day)
            for hour in range(8, 20):  # 8 AM to 8 PM
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                timestamp = base_time.replace(hour=hour, minute=minute, second=second)
                logs.append(f'{timestamp.strftime("%Y-%m-%d %H:%M:%S")} [INFO] wlogs: LOGS : "{username}" has draw')

        # Create in-memory file
        buffer = StringIO()
        buffer.write("\n".join(logs))
        buffer.seek(0)

        # Send as Discord file
        await ctx.send(file=discord.File(fp=buffer, filename=f"{username}_draw_logs.txt"))

async def setup(bot):
    await bot.add_cog(WLogs(bot))
