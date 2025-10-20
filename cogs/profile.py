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

    @commands.command(name="profile")
    async def profile(self, ctx, member: discord.Member = None):
        user = member or ctx.author
        user_id = user.id

        async with self.bot.db.acquire() as conn:
            profile = await conn.fetchrow("""
                SELECT user_id, username, bloodcoins, noble_coins, level, xp, xp_next,
                       created_at, updated_at, buddy_card_id, badges, equipment,
                       banned, ban_reason
                FROM users
                WHERE user_id = $1
            """, user_id)

            if not profile:
                await ctx.send("⚠️ This user does not have a profile yet.")
                return

            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE c.form = 'base') AS base,
                    COUNT(*) FILTER (WHERE c.form = 'awakened') AS awakened,
                    COUNT(*) FILTER (WHERE c.form = 'event') AS event,
                    MAX(uc.xp) AS buddy_xp
                FROM user_cards uc
                JOIN cards c ON c.id = uc.card_id
                WHERE uc.user_id = $1
            """, user_id)

            buddy = None
            if profile["buddy_card_id"]:
                buddy = await conn.fetchrow("""
                    SELECT character_name, image_url
                    FROM cards
                    WHERE id = $1
                """, profile["buddy_card_id"])

        embed = discord.Embed(
            title=f"👤 Profile of {user.display_name}",
            color=discord.Color.gold() if (stats and stats["awakened"]) else discord.Color.blurple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="💰 BloodCoins", value=f"{profile['bloodcoins']:,}", inline=True)
        embed.add_field(name="💎 Noble Coins", value=f"{profile['noble_coins']:,}", inline=True)

        xp = profile.get("xp", 0) or 0
        xp_next = profile.get("xp_next", 100) or 100
        level = profile.get("level", 1) or 1
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

        if profile["banned"]:
            reason = profile["ban_reason"] or "No reason provided"
            embed.add_field(name="⛔ Account Status", value=f"BANNED\nReason: {reason}", inline=False)

        if stats:
            collection = (
                f"**Total:** {stats['total'] or 0}\n"
                f"{FORM_EMOJIS['base']} {stats['base'] or 0} | "
                f"{FORM_EMOJIS['awakened']} {stats['awakened'] or 0} | "
                f"{FORM_EMOJIS['event']} {stats['event'] or 0}"
            )
            embed.add_field(name="🃏 Collection", value=collection, inline=False)

        if stats["buddy_xp"]:
            level = stats["buddy_xp"] // 100 + 1
            embed.add_field(name="🐾 Buddy Level", value=f"Lvl {level} ({stats['buddy_xp']} XP)", inline=True)

        if buddy:
            embed.add_field(name="🐾 Buddy", value=buddy["character_name"], inline=False)
            if buddy["image_url"]:
                embed.set_image(url=buddy["image_url"])

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
