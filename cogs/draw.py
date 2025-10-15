import discord
from discord.ext import commands

class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="draw")
    async def draw(self, ctx):
        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT card_id, name, rarity, potential, image_url, description
                FROM cards
                ORDER BY random()
                LIMIT 1
            """)

        if not card:
            await ctx.send("Aucune carte disponible.")
            return

        # Choix de la couleur selon la rareté
        rarity_colors = {
            "common": discord.Color.light_gray(),
            "rare": discord.Color.blue(),
            "epic": discord.Color.purple(),
            "legendary": discord.Color.gold()
        }
        color = rarity_colors.get(card["rarity"], discord.Color.dark_gray())

        # Création de l'embed
        embed = discord.Embed(
            title=f"✨ Tu as obtenu : {card['name']} ✨",
            description=card["description"] or "Pas de description disponible.",
            color=color
        )
        embed.add_field(name="Rareté", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Potentiel", value=str(card["potential"]), inline=True)

        if card["image_url"]:
            embed.set_thumbnail(url=card["image_url"])

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Draw(bot))
