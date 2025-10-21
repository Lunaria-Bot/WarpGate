import discord
from discord.ext import commands

FORM_EMOJIS = {
    "base": "🟦",
    "awakened": "✨",
    "event": "🎉"
}

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["p"])
    async def profile(self, ctx, member: discord.Member = None):
        user = member or ctx.author
        discord_id = str(user.id)

        async with self.bot.db.acquire() as conn:
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
                FROM cards c
                WHERE c.owner_id = (
                    SELECT id FROM players WHERE discord_id = $1
                )
            """, discord_id)

        embed = discord.Embed(
            title=f"👤 Profile of {user.display_name}",
            color=discord.Color.gold() if (stats and stats["awakened"]) else discord.Color.blurple()
        )
        embed.set_thumbnail(url=profile["avatar_url"] or user.display_avatar.url)

        embed.add_field(name="💰 BloodCoins", value=f"{profile['bloodcoins']:,}", inline=True)
        embed.add_field(name="💎 Noble Coins", value=f"{profile['noblecoins']:,}", inline=True)

        xp = profile["xp"] or 0
        level = profile["level"] or 1
        xp_next = 172
        progress = int((xp / xp_next) * 20) if xp_next else 0
        bar = "█" * progress + "░" * (20 - progress)
        embed.add_field(
            name="📈 Level",
            value=f"Lvl {level} | {xp}/{xp_next} XP\n`{bar}`",
            inline=False
        )

        if profile["created_at"]:
            embed.add_field(name="📅 Created", value=profile["created_at"].strftime("%d %b %Y"), inline=True)
        if profile["updated_at"]:
            embed.add_field(name="🔄 Last Update", value=profile["updated_at"].strftime("%d %b %Y"), inline=True)

        if stats:
            collection = (
                f"**Total:** {stats['total'] or 0}\n"
                f"{FORM_EMOJIS['base']} {stats['base'] or 0} | "
                f"{FORM_EMOJIS['awakened']} {stats['awakened'] or 0} | "
                f"{FORM_EMOJIS['event']} {stats['event'] or 0}"
            )
            embed.add_field(name="🃏 Collection", value=collection, inline=False)

        achievements = []
        if stats and stats["awakened"]:
            achievements.append("✨ Awakened Collector")
        if profile["bloodcoins"] > 100000:
            achievements.append("💎 Wealthy")
        if level >= 10:
            achievements.append("⭐ Level 10+")
        embed.add_field(name="🎖️ Achievements", value=", ".join(achievements) or "—", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Profile(bot))
