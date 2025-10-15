import discord
from discord.ext import commands

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

RARITY_ORDER = ["common", "rare", "epic", "legendary"]

class RaritySelect(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="All", value="all", description="Show all rarities"),
            discord.SelectOption(label="Common", value="common"),
            discord.SelectOption(label="Rare", value="rare"),
            discord.SelectOption(label="Epic", value="epic"),
            discord.SelectOption(label="Legendary", value="legendary"),
        ]
        super().__init__(placeholder="Filter by rarity…", options=options, min_values=1, max_values=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        rarity = self.values[0]
        self.parent_view.current_rarity = rarity
        # Met à jour le menu des cartes
        self.parent_view.update_card_select()
        await interaction.response.edit_message(embed=self.parent_view.base_embed, view=self.parent_view)


class CardSelect(discord.ui.Select):
    def __init__(self, parent_view, cards):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=f"{c['name']} ({c['rarity'].capitalize()})",
                description=f"Qty: {c['quantity']}",
                value=str(c['card_id'])
            )
            for c in cards[:25]  # Discord limite à 25 options
        ]
        super().__init__(placeholder="Select a card to view details…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        card_id = int(self.values[0])
        card = next((c for c in self.parent_view.cards if c["card_id"] == card_id), None)

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

        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class InventoryView(discord.ui.View):
    def __init__(self, cards, base_embed):
        super().__init__(timeout=120)
        self.cards = cards
        self.base_embed = base_embed
        self.current_rarity = "all"

        # Ajoute le filtre de rareté
        self.add_item(RaritySelect(self))
        # Ajoute le sélecteur de cartes
        self.card_select = None
        self.update_card_select()

    def update_card_select(self):
        # Supprime l’ancien sélecteur si présent
        if self.card_select:
            self.remove_item(self.card_select)

        # Filtre les cartes
        if self.current_rarity == "all":
            filtered = self.cards
        else:
            filtered = [c for c in self.cards if c["rarity"] == self.current_rarity]

        if not filtered:
            filtered = [{"card_id": -1, "name": "No cards", "rarity": "none", "quantity": 0, "potential": 0, "description": "", "image_url": None}]

        self.card_select = CardSelect(self, filtered)
        self.add_item(self.card_select)


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        """Show the user's inventory with rarity filter and card selector."""
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

        # Embed de base
        embed = discord.Embed(
            title=f"🎴 {ctx.author.display_name}'s Inventory",
            description=f"💰 Bloodcoins: **{balance}**\nUse the menus below to filter and view cards.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        view = InventoryView(rows, embed)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
