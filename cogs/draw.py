import discord
from discord.ext import commands
import asyncio
import random

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

# --- Mimic data ---
MIMIC_QUOTES = [
    "Treasure? Oh no, I’m the real reward.",
    "Curiosity tastes almost as good as fear.",
    "Funny how you never suspect the things you want most."
]

MIMIC_IMAGE = "https://media.discordapp.net/attachments/1428401795364814948/1428401824024756316/image.png?format=webp&quality=lossless&width=880&height=493"

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


class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="draw")
    @commands.cooldown(1, 600, commands.BucketType.user)  # 1 utilisation toutes les 600s (10 min) par joueur
    async def draw(self, ctx):
        """Draw a card with a 10% chance of encountering a Mimic instead.
        +10 Bloodcoins per draw, updates quest progress, 10 min cooldown per user.
        """
        # 1. Animation GIF
        embed = discord.Embed(description="🎴 Drawing in progress...")
        embed.set_image(
            url="https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif"
        )
        anim_msg = await ctx.send(embed=embed)

        await asyncio.sleep(2)

        # 2. Check Mimic encounter (10%)
        if random.randint(1, 100) <= 10:
            quote = random.choice(MIMIC_QUOTES)
            mimic_embed = discord.Embed(
                title="👾 A wild Mimic appears!",
                description=f"_{quote}_\n\nAs you saw him you ran away (Update coming soon)",
                color=discord.Color.dark_red()
            )
            mimic_embed.set_image(url=MIMIC_IMAGE)
            await anim_msg.edit(embed=mimic_embed, content=None, attachments=[])
            return

        # 3. Normal draw logic
        user_id = int(ctx.author.id)

        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT card_id, base_name, name, rarity, potential, image_url, description
                FROM cards
                WHERE rarity = 'common'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await anim_msg.edit(content="⚠️ No common cards available in the database.")
                return

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, user_id, card["card_id"])

            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10
                WHERE user_id = $1
            """, user_id)

            await update_quest_progress(conn, user_id, "Draw 5 times", 1)
            await update_quest_progress(conn, user_id, "Draw 10 times", 1)
            await update_quest_progress(conn, user_id, "Draw 100 times", 1)

        rarity = card["rarity"]
        potential = int(card["potential"]) if card["potential"] is not None else 0

        result_embed = discord.Embed(
            title=f"✨ You drew: {card['name']} ✨",
            description=card["description"] or "No description available.",
            color=RARITY_COLORS.get(rarity, discord.Color.dark_gray())
        )
        result_embed.add_field(name="Rarity", value=rarity.capitalize(), inline=True)
        result_embed.add_field(name="Potential", value="⭐" * potential, inline=True)

        if card["image_url"]:
            result_embed.set_thumbnail(url=card["image_url"])

        await anim_msg.edit(content=None, attachments=[], embed=result_embed)

    @draw.error
    async def draw_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = int(error.retry_after // 60)
            seconds = int(error.retry_after % 60)
            await ctx.send(
                f"⏳ Tu dois attendre encore **{minutes}m {seconds}s** avant de pouvoir utiliser `!draw` à nouveau.",
                delete_after=10
            )


async def setup(bot):
    await bot.add_cog(Draw(bot))
