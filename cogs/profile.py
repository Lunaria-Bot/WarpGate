import discord
from discord.ext import commands

RARITY_EMOJIS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡"
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
                       created_at, updated_at, buddy_card_id, badges, equipment
                FROM users
                WHERE user_id = $1
            """, user_id)

            if not profile:
                await ctx.send("⚠️ This user does not have a profile yet.")
                return

            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN c.rarity = 'common' THEN uc.quantity ELSE 0 END) AS commons,
                    SUM(CASE WHEN c.rarity = 'rare' THEN uc.quantity ELSE 0 END) AS rares,
                    SUM(CASE WHEN c.rarity = 'epic' THEN uc.quantity ELSE 0 END) AS epics,
                    SUM(CASE WHEN c.rarity = 'legendary' THEN uc.quantity ELSE 0 END) AS legendaries
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
            """, user_id)

            buddy = None
            if profile["buddy_card_id"]:
                buddy = await conn.fetchrow("""
                    SELECT name, image_url
                    FROM cards
                    WHERE card_id = $1
                """, profile["buddy_card_id"])

        # --- Embed ---
        embed = discord.Embed(
            title=f"👤 Profile of {user.display_name}",
            color=discord.Color.gold() if (stats and stats["legendaries"]) else discord.Color.blurple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        # Currency
        embed.add_field(name="💰 BloodCoins", value=f"{profile['bloodcoins']:,}", inline=True)
        embed.add_field(name="💎 Noble Coins", value=f"{profile['noble_coins']:,}", inline=True)

        # Level & XP
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

        # Dates
        if profile["created_at"]:
            embed.add_field(name="📅 Created", value=profile["created_at"].strftime("%d %b %Y"), inline=True)
        if profile["updated_at"]:
            embed.add_field(name="🔄 Last Update", value=profile["updated_at"].strftime("%d %b %Y"), inline=True)

        # Collection
        if stats:
            collection = (
                f"**Total:** {stats['total'] or 0}\n"
                f"{RARITY_EMOJIS['common']} {stats['commons'] or 0} | "
                f"{RARITY_EMOJIS['rare']} {stats['rares'] or 0} | "
                f"{RARITY_EMOJIS['epic']} {stats['epics'] or 0} | "
                f"{RARITY_EMOJIS['legendary']} {stats['legendaries'] or 0}"
            )
            embed.add_field(name="🃏 Collection", value=collection, inline=False)

        # Buddy
        if buddy:
            embed.add_field(name="🐾 Buddy", value=buddy["name"], inline=False)
            if buddy["image_url"]:
                embed.set_image(url=buddy["image_url"])

        # Achievements / Badges
        achievements = []
        if stats and stats["legendaries"]:
            achievements.append("🏆 Legendary Owner")
        if profile["bloodcoins"] > 100000:
            achievements.append("💎 Wealthy")
        if level >= 10:
            achievements.append("⭐ Level 10+")
        embed.add_field(name="🎖️ Achievements", value=", ".join(achievements) or "—", inline=False)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))
