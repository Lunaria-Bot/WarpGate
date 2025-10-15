import random
import discord
from discord.ext import commands
import asyncio

# Probabilités de tirage par rareté
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
        # 1. Créer l'embed avec le GIF
        embed = discord.Embed(description="🎴 Tirage en cours...")
        embed.set_image(
            url="https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif"
        )

        # 2. Envoyer l'embed
        anim_msg = await ctx.send(embed=embed)

        # 3. Attendre un délai avant de révéler la carte
        await asyncio.sleep(2)

        # 4. Tirage de la rareté selon les poids
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

        async with self.bot.db.acquire() as conn:
            # 5. Tirage d'une carte dans cette rareté
            card = await conn.fetchrow("""
                SELECT card_id, name, rarity, potential, image_url, description
                FROM cards
                WHERE rarity = $1
                ORDER BY random()
                LIMIT 1
            """, chosen_rarity)

            if not card:
                await anim_msg.edit(content="❌ Aucune carte disponible.")
                return

            # 6. Enregistrement dans user_cards (UPSERT)
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, ctx.author.id, card["card_id"])

        # 7. Embed résultat
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

        # 8. Remplacer le GIF par le résultat
        await anim_msg.edit(content=None, attachments=[], embed=result_embed)


async def setup(bot):
    await bot.add_cog(Draw(bot))
