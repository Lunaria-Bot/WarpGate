import discord
from discord.ext import commands

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

class CardSelect(discord.ui.Select):
    def __init__(self, cards):
        options = [
            discord.SelectOption(
                label=f"{c['name']} ({c['rarity'].capitalize()})",
                description=f"Qty: {c['quantity']}",
                value=str(c['card_id'])
            )
            for c in cards
        ]
        super().__init__(placeholder="Select a card to view details…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        # Récupère la carte choisie
        card_id = int(self.values[0])
        card = next((c for c in self.view.cards if c["card_id"] == card_id), None)

        if not card:
            await interaction.response.send_message("⚠️ Card not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{card['name']}",
            description=card["description"] or "No description available.",
            color=RARITY_COLORS.get(card["rarity"], discord.Color.dark_gray())
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Quantity", value=str(card["quantity"]), inline=True)
        embed.add_field(name="Potential", value="⭐" * int(card["potential"]), inline=True)

        if card["image_url"]:
            embed.set_image(url=card["image_url"])

        await interaction.response.edit_message(embed=embed, view=self.view)


class InventoryView(discord.ui.View):
    def __init__(self, cards):
        super().__init__(timeout=120)
        self.cards = cards
        self.add_item(CardSelect(cards))


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        """Show the user's inventory with a card selector."""
        user_id = int(ctx.author.id)

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.card_id, c.base_name, c.name, c.rarity, c.potential, c.image_url, c.description, uc.quantity
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
                ORDER BY 
                    CASE c.rarity
                        WHEN 'legendary' THEN 1
                        WHEN 'epic' THEN 2
                        WHEN 'rare' THEN 3
                        ELSE 4
                    END,
                    c.base_name
            """, user_id)

            balance = await conn.fetchval(
                "SELECT bloodcoins FROM users WHERE user_id = $1", user_id
            )

        if not rows:
            await ctx.send("📭 Your inventory is empty. Use `!draw` to get cards!")
            return

        # Embed de base (liste des cartes)
        embed = discord.Embed(
            title=f"🎴 {ctx.author.display_name}'s Inventory",
            description=f"💰 Bloodcoins: **{balance}**\nSelect a card below to view details.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        for row in rows[:10]:  # affiche un aperçu des 10 premières
            embed.add_field(
                name=f"{row['name']} ({row['rarity'].capitalize()})",
                value=f"Qty: {row['quantity']}",
                inline=False
            )

        view = InventoryView(rows)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
