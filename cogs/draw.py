import random
import discord
from discord.ext import commands
import asyncio

# Draw probabilities by rarity
RARITY_WEIGHTS = {
    "common": 65,
    "rare": 30,
    "epic": 4,
    "legendary": 0.5
}

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="draw")
    async def draw(self, ctx):
        # 1. Send an animation GIF (always the same one)
        embed = discord.Embed(description="🎴 Drawing in progress...")
        embed.set_image(
            url="https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif"
        )
        anim_msg = await ctx.send(embed=embed)

        # 2. Wait a short delay before revealing the card
        await asyncio.sleep(2)

        # 3. Pick a rarity based on weights
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

        async with self.bot.db.acquire() as conn:
            # 4. Pick a random card of that rarity
            card = await conn.fetchrow("""
                SELECT card_id, name, rarity, potential, image_url, description
                FROM cards
                WHERE rarity = $1
                ORDER BY random()
                LIMIT 1
            """, chosen_rarity)

            # Safety check: no card found
            if not card:
                await ctx.send(f"⚠️ No card available for rarity '{chosen_rarity}'. Please check your database.")
                return

            # 5. Insert or update the user's card (UPSERT)
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, ctx.author.id, card["card_id"])

        # 6. Build the result embed
        color = RARITY_COLORS.get(card["rarity"], discord.Color.dark_gray())
        result_embed = discord.Embed(
            title=f"✨ You drew: {card['name']} ✨",
            description=card["description"] or "No description available.",
            color=color
        )
        result_embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        result_embed.add_field(name="Potential", value="⭐" * card["potential"], inline=True)

        if card["image_url"]:
            result_embed.set_thumbnail(url=card["image_url"])

        # 7. Replace the GIF with the result
        await anim_msg.edit(content=None, attachments=[], embed=result_embed)


async def setup(bot):
    await bot.add_cog(Draw(bot))
