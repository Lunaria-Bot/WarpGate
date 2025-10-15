import discord
from discord.ext import commands

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory")
    async def inventory(self, ctx, member: discord.Member = None):
        """Affiche l'inventaire de cartes d'un joueur."""
        target = member or ctx.author

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.name, c.rarity, c.potential, uc.quantity
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
                ORDER BY c.rarity DESC, c.name
            """, target.id)

        if not rows:
            await ctx.send(f"{target.display_name} n'a aucune carte.")
            return

        # Construction de l'embed
        embed = discord.Embed(
            title=f"📦 Inventory of {target.display_name}",
            color=discord.Color.blue()
        )

        for row in rows:
            stars = "⭐" * row["potential"]
            embed.add_field(
                name=f"{row['name']} ({row['rarity'].capitalize()})",
                value=f"Qty: {row['quantity']} | Potential: {stars}",
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Inventory(bot))
