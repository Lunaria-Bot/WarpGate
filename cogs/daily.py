import discord
from discord.ext import commands
import datetime
from utils.leveling import add_xp
from utils.db import db_transaction  # helper context manager

# --- Helper: update quest progress ---
async def update_quest_progress(conn, user_id: int, quest_desc: str, amount: int = 1):
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

# --- Helper: gain buddy XP ---
async def gain_buddy_xp(bot, user_id: int, amount: int):
    async with db_transaction(bot.db) as conn:
        buddy_id = await conn.fetchval("SELECT buddy_card_id FROM users WHERE user_id = $1", user_id)
        if not buddy_id:
            return

        await conn.execute("""
            UPDATE user_cards
            SET xp = xp + $1,
                health = 100 + ((xp + $1) / 100)::int * 5,
                attack = 10 + ((xp + $1) / 100)::int * 2,
                speed = 10 + ((xp + $1) / 100)::int * 1
            WHERE user_id = $2 AND card_id = $3
        """, amount, user_id, buddy_id)

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.command(name="daily")
    async def daily(self, ctx):
        user_id = int(ctx.author.id)
        now = datetime.datetime.utcnow()

        today_midnight = datetime.datetime.combine(now.date(), datetime.time.min)
        tomorrow_midnight = today_midnight + datetime.timedelta(days=1)

        last_claim = self.cooldowns.get(user_id)
        if last_claim and last_claim >= today_midnight:
            remaining = (tomorrow_midnight - now).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await ctx.send(
                f"⏳ You already claimed your daily. Next reset in {hours}h {minutes}m "
                f"(<t:{int(tomorrow_midnight.timestamp())}:R>)."
            )
            return

        async with db_transaction(self.bot.db) as conn:
            await conn.execute("""
                UPDATE users SET bloodcoins = bloodcoins + 10000 WHERE user_id = $1
            """, user_id)

            await update_quest_progress(conn, user_id, "Do !daily", 1)
            await update_quest_progress(conn, user_id, "Do 5 !daily", 1)

        self.cooldowns[user_id] = now

        await gain_buddy_xp(self.bot, user_id, amount=5)
        leveled_up, new_level = await add_xp(self.bot, user_id, 10)

        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"✅ {ctx.author.display_name}, you received **10,000 Bloodcoins**!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        if leveled_up:
            embed.add_field(name="📈 Level Up", value=f"You reached **Level {new_level}**!", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Daily(bot))
