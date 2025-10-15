import discord
from discord.ext import commands

MAX_OPTIONS = 9  # 9 cartes par page

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

class CardSelect(discord.ui.Select):
    def __init__(self, cards, page, total_pages, total_count):
        options = [
            discord.SelectOption(
                label=f"{c['name']} x{c['quantity']}",
                description=f"{c['rarity'].capitalize()} | ⭐{c['potential']}",
                value=c['card_id']
            )
            for c in cards
        ]
        super().__init__(
            placeholder=f"Page {page+1}/{total_pages} – {total_count} cartes",
            options=options, min_values=1, max_values=1
        )
        self.cards = {c['card_id']: c for c in cards}

    async def callback(self, interaction: discord.Interaction):
        card = self.cards[self.values[0]]
        color = RARITY_COLORS.get(card["rarity"], discord.Color.dark_gray())

        embed = discord.Embed(
            title=card["name"],
            description=card["description"] or "No description.",
            color=color
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Potential", value="⭐" * card["potential"], inline=True)
        embed.add_field(name="Quantity", value=str(card["quantity"]), inline=True)

        if card["image_url"]:
            embed.set_image(url=card["image_url"])

        await interaction.response.edit_message(embed=embed, view=self.view)


class RarityFilter(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="All", value="all", description="Toutes les cartes"),
            discord.SelectOption(label="Common", value="common"),
            discord.SelectOption(label="Rare", value="rare"),
            discord.SelectOption(label="Epic", value="epic"),
            discord.SelectOption(label="Legendary", value="legendary"),
        ]
        super().__init__(placeholder="Filtrer par rareté…", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.filter_rarity = self.values[0]
        self.parent_view.page = 0
        self.parent_view.update_view()
        await interaction.response.edit_message(embed=self.parent_view.embed, view=self.parent_view)


class InventoryView(discord.ui.View):
    def __init__(self, cards):
        super().__init__(timeout=180)
        self.all_cards = cards
        self.filter_rarity = "all"
        self.page = 0
        self.update_view()

    def get_filtered_cards(self):
        if self.filter_rarity == "all":
            return self.all_cards
        return [c for c in self.all_cards if c["rarity"] == self.filter_rarity]

    def update_view(self):
        self.clear_items()
        filtered = self.get_filtered_cards()
        total_count = len(filtered)
        self.total_pages = max(1, (total_count - 1) // MAX_OPTIONS + 1)

        start = self.page * MAX_OPTIONS
        end = start + MAX_OPTIONS
        page_cards = filtered[start:end]

        # Embed liste compacte
        desc = "\n".join(
            f"• {c['name']} ({c['rarity'].capitalize()}) x{c['quantity']}"
            for c in page_cards
        ) or "Aucune carte"
        self.embed = discord.Embed(
            title=f"📦 Inventory (Page {self.page+1}/{self.total_pages} – {total_count} cartes)",
            description=desc,
            color=discord.Color.blue()
        )

        if page_cards:
            self.add_item(CardSelect(page_cards, self.page, self.total_pages, total_count))

        # Ajout du filtre
        self.add_item(RarityFilter(self))

        # Pagination
        if self.total_pages > 1:
            self.add_item(PrevButton())
            self.add_item(NextButton())


class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬅️")

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        if view.page > 0:
            view.page -= 1
            view.update_view()
            await interaction.response.edit_message(embed=view.embed, view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="➡️")

    async def callback(self, interaction: discord.Interaction):
        view: InventoryView = self.view
        if view.page < view.total_pages - 1:
            view.page += 1
            view.update_view()
            await interaction.response.edit_message(embed=view.embed, view=view)


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory")
    async def inventory(self, ctx, member: discord.Member = None):
        """Affiche l'inventaire avec pagination et filtre par rareté."""
        target = member or ctx.author

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.card_id, c.name, c.rarity, c.potential, c.image_url, c.description, uc.quantity
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
                ORDER BY c.rarity DESC, c.name
            """, target.id)

        if not rows:
            await ctx.send(f"{target.display_name} n'a aucune carte.")
            return

        cards = [dict(row) for row in rows]

        view = InventoryView(cards)
        await ctx.send(embed=view.embed, view=view)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
