import discord
from discord.ext import commands
import datetime

# --- Helper: update quest progress ---
async def update_quest_progress(conn, user_id: int, quest_desc: str, amount: int = 1):
    """Increment quest progress for a given quest description."""
    await conn.execute("""
        UPDATE user_quests uq
        SET progress = progress + $3,
            completed = (progress + $3) >= qt.target
        FROM quest_templates qt
        WHERE uq.quest_id = qt.quest_id
          AND uq.user_id = $1
          AND qt.description = $2
          AND uq.claimed = FALSE
    """, user_id, quest_desc, amount)


class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}  # {user_id: datetime of last claim}

    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily 10,000 Bloodcoins reward and update quests."""
        user_id = int(ctx.author.id)
        now = datetime.datetime.utcnow()

        # Calculate today's and tomorrow's midnight UTC
        today_midnight = datetime.datetime.combine(now.date(), datetime.time.min)
        tomorrow_midnight = today_midnight + datetime.timedelta(days=1)

        last_claim = self.cooldowns.get(user_id)
        if last_claim and last_claim >= today_midnight:
            # Already claimed today
            remaining = (tomorrow_midnight - now).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await ctx.send(
                f"⏳ You already claimed your daily. Next reset in {hours}h {minutes}m "
                f"(<t:{int(tomorrow_midnight.timestamp())}:R>)."
            )
            return

        async with self.bot.db.acquire() as conn:
            # Reward coins
            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10000
                WHERE user_id = $1
            """, user_id)

            # ✅ Update quest progress
            await update_quest_progress(conn, user_id, "Do !daily", 1)
            await update_quest_progress(conn, user_id, "Do 5 !daily", 1)

        # Save last claim timestamp
        self.cooldowns[user_id] = now

        # Confirmation embed
        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"✅ {ctx.author.display_name}, you received **10,000 Bloodcoins**!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Daily(bot))
