import discord
from discord.ext import commands
from typing import Optional
from utils.db import db_transaction

FORM_EMOJIS = {
    "base": "🟦",
    "awakened": "✨",
    "event": "🎉"
}

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["p"])
    async def profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        user = member or ctx.author
        discord_id = str(user.id)

        async with db_transaction(self.bot.db) as conn:
            profile = await conn.fetchrow("""
                SELECT discord_id, name, bloodcoins, noblecoins, level, xp,
                       created_at, updated_at, achievements, avatar_url
                FROM players
                WHERE discord_id = $1
            """, discord_id)

            if not profile:
                await ctx.send("⚠️ This user does not have a profile yet.")
                return

            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE c.form = 'base') AS base,
                    COUNT(*) FILTER (WHERE c.form = 'awakened') AS awakened,
                    COUNT(*) FILTER (WHERE c.form = 'event') AS event
                FROM user_cards uc
                JOIN cards c ON c.id = uc.card_id
                WHERE uc.user_id = (
                    SELECT id FROM players WHERE discord_id = $1
                )
            """, discord_id)

        # 🎨 Embed setup
        color = discord.Color.gold() if stats and stats["awakened"] else discord.Color.blurple()
        embed = discord.Embed(
            title=f"👤 Profile of {user.display_name}",
            color=color
        )
        embed.set_thumbnail(url=profile["avatar_url"] or user.display_avatar.url)

        # 💰 Currency
        embed.add_field(name="💰 BloodCoins", value=f"{profile['bloodcoins']:,}", inline=True)
        embed.add_field(name="💎 Noble Coins", value=f"{profile['noblecoins']:,}", inline=True)

        # 📈 Level & XP
        level = profile["level"] or 1
        xp = profile["xp"] or 0
        xp_next = 172
        progress = int((xp / xp_next) * 20)
        bar = "▰" * progress + "▱" * (20 - progress)
        embed.add_field(
            name="📈 Level",
            value=f"Lvl {level} • {xp}/{xp_next} XP\n`{bar}`",
            inline=False
        )

        # 📅 Dates
        if profile["created_at"]:
            embed.add_field(name="📅 Created", value=profile["created_at"].strftime("%d %b %Y"), inline=True)
        if profile["updated_at"]:
            embed.add_field(name="🔄 Last Update", value=profile["updated_at"].strftime("%d %b %Y"), inline=True)

        # 🃏 Collection
        if stats:
            collection = (
                f"**Total:** {stats['total'] or 0}\n"
                f"{FORM_EMOJIS['base']} {stats['base'] or 0} | "
                f"{FORM_EMOJIS['awakened']} {stats['awakened'] or 0} | "
                f"{FORM_EMOJIS['event']} {stats['event'] or 0}"
            )
            embed.add_field(name="🃏 Collection", value=collection, inline=False)

        # 🎖️ Achievements
        achievements = []
        if stats and stats["awakened"]:
            achievements.append("✨ Awakened Collector")
        if profile["bloodcoins"] > 100_000:
            achievements.append("💎 Wealthy")
        if level >= 10:
            achievements.append("⭐ Level 10+")
        embed.add_field(name="🎖️ Achievements", value=", ".join(achievements) or "—", inline=False)

        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
