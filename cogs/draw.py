import discord
from discord.ext import commands
import asyncio

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
        # 1. Show animation GIF
        embed = discord.Embed(description="🎴 Drawing in progress...")
        embed.set_image(
            url="https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif"
        )
        anim_msg = await ctx.send(embed=embed)

        await asyncio.sleep(2)

        async with self.bot.db.acquire() as conn:
            # 2. Always pick a Common card
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

            # 3. Insert or update user inventory
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, ctx.author.id, card["card_id"])

        # 4. Show result
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


async def setup(bot):
    await bot.add_cog(Draw(bot))
