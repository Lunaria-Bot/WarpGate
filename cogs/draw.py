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
            await ctx.send("No cards available.")
            return

        # Color mapping by rarity
        rarity_colors = {
            "common": discord.Color.light_gray(),
            "rare": discord.Color.blue(),
            "epic": discord.Color.purple(),
            "legendary": discord.Color.gold()
        }
        color = rarity_colors.get(card["rarity"], discord.Color.dark_gray())

        # Build the embed
        embed = discord.Embed(
            title=f"✨ You drew: {card['name']} ✨",
            description=card["description"] or "No description available.",
            color=color
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Potential", value=str(card["potential"]), inline=True)

        if card["image_url"]:
            embed.set_thumbnail(url=card["image_url"])

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Draw(bot))
