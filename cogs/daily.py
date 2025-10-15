import discord
from discord.ext import commands
import datetime

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}  # simple in-memory cooldown {user_id: datetime}

    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily 10,000 Bloodcoins reward."""
        user_id = int(ctx.author.id)
        now = datetime.datetime.utcnow()

        # Vérifier si le joueur a déjà pris son daily
        last_claim = self.cooldowns.get(user_id)
        if last_claim and (now - last_claim).total_seconds() < 86400:
            remaining = 86400 - (now - last_claim).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await ctx.send(f"⏳ You already claimed your daily. Try again in {hours}h {minutes}m.")
            return

        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10000
                WHERE user_id = $1
            """, user_id)

        self.cooldowns[user_id] = now

        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"✅ {ctx.author.display_name}, you received **10,000 Bloodcoins**!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Daily(bot))
