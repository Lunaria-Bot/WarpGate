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
        url="https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif?ex=68f0f540&is=68efa3c0&hm=48143b857f5152e9e9c780bc66b65c1838b985a42f93da75cd333a774214bd67&=&width=440&height=248"
    )

    # 2. Envoyer l'embed
    anim_msg = await ctx.send(embed=embed)

    # 3. Attendre un délai avant de révéler la carte
    await asyncio.sleep(2)

    # … ici tu continues avec le tirage de la carte et l’édition du message

        # 2. Attendre un petit délai (2 secondes par ex.)
        await asyncio.sleep(2)

        # 3. Tirage de la rareté selon les poids
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

        async with self.bot.db.acquire() as conn:
            # 4. Tirage d'une carte dans cette rareté
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

            # 5. Enregistrement dans user_cards (UPSERT)
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, ctx.author.id, card["card_id"])

        # 6. Embed résultat
        color = RARITY_COLORS.get(card["rarity"], discord.Color.dark_gray())
        embed = discord.Embed(
            title=f"✨ You drew: {card['name']} ✨",
            description=card["description"] or "No description available.",
            color=color
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Potential", value="⭐" * card["potential"], inline=True)

        if card["image_url"]:
            embed.set_thumbnail(url=card["image_url"])

        # 7. Remplacer le GIF par le résultat
        await anim_msg.edit(content=None, attachments=[], embed=embed)


async def setup(bot):
    await bot.add_cog(Draw(bot))
