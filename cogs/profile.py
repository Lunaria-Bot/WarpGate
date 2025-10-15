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
        """Show the profile of a user (default: yourself)."""
        user = member or ctx.author
        user_id = int(user.id)  # ✅ force int

        async with self.bot.db.acquire() as conn:
            # 1. Fetch user data
            profile = await conn.fetchrow("""
                SELECT user_id, bloodcoins, created_at, updated_at
                FROM users
                WHERE user_id = $1
            """, user_id)

            if not profile:
                await ctx.send("⚠️ This user does not have a profile yet.")
                return

            # 2. Fetch card collection stats
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

        # 3. Build embed
        embed = discord.Embed(
            title=f"👤 Profile of {user.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(
            name="💰 Balance",
            value=f"{profile['bloodcoins']:,} BloodCoins",
            inline=False
        )

        embed.add_field(
            name="🃏 Card Collection",
            value=(
                f"**Total:** {stats['total'] or 0}\n"
                f"{RARITY_EMOJIS['common']} Commons: {stats['commons'] or 0}\n"
                f"{RARITY_EMOJIS['rare']} Rares: {stats['rares'] or 0}\n"
                f"{RARITY_EMOJIS['epic']} Epics: {stats['epics'] or 0}\n"
                f"{RARITY_EMOJIS['legendary']} Legendaries: {stats['legendaries'] or 0}"
            ),
            inline=False
        )

        embed.add_field(
            name="📅 Joined",
            value=profile["created_at"].strftime("%d %B %Y"),
            inline=True
        )

        if "updated_at" in profile and profile["updated_at"]:
            embed.add_field(
                name="🔄 Last Update",
                value=profile["updated_at"].strftime("%d %B %Y"),
                inline=True
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))
