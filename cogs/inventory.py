import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from .entities import entity_from_db, RARITY_BASE_STATS  # use stat hierarchy

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

RARITY_ORDER = ["legendary", "epic", "rare", "common"]


def format_stats_inline(card_row, user_card_row=None):
    """
    Returns a short inline stats string using the same precedence as entity_from_db:
    user_cards > cards > rarity base.
    """
    # Build effective stats
    h = user_card_row.get("health") if user_card_row and user_card_row.get("health") is not None else card_row.get("health")
    a = user_card_row.get("attack") if user_card_row and user_card_row.get("attack") is not None else card_row.get("attack")
    s = user_card_row.get("speed") if user_card_row and user_card_row.get("speed") is not None else card_row.get("speed")

    if h is None or a is None or s is None:
        base = RARITY_BASE_STATS.get(card_row["rarity"], RARITY_BASE_STATS["common"])
        h = base["health"] if h is None else h
        a = base["attack"] if a is None else a
        s = base["speed"] if s is None else s

    return f"❤️ {h} | 🗡️ {a} | ⚡ {s}"


class RaritySelect(Select):
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
        self.parent_view.current_rarity = self.values[0]
        self.parent_view.page = 0  # reset pagination
        self.parent_view.update_card_select()
        await interaction.response.edit_message(embed=self.parent_view.format_page(), view=self.parent_view)


class CardSelect(Select):
    def __init__(self, parent_view, cards):
        self.parent_view = parent_view
        # Discord limits to 25 options; we show the first page's items via InventoryView logic
        options = []
        for c in cards[:25]:
            stats_preview = format_stats_inline(
                c,
                {"health": c.get("u_health"), "attack": c.get("u_attack"), "speed": c.get("u_speed")}
            )
            options.append(
                discord.SelectOption(
                    label=f"{c['name']} ({c['rarity'].capitalize()})",
                    description=f"Qty: {c['quantity']} • {stats_preview}",
                    value=str(c['card_id'])
                )
            )
        super().__init__(placeholder="Select a card to view details…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        card_id = int(self.values[0])
        card = next((c for c in self.parent_view.cards if c["card_id"] == card_id), None)

        if not card:
            await interaction.response.send_message("⚠️ Card not found.", ephemeral=True)
            return

        # Build entity using DB rows for full stat hierarchy
        user_card_row = {"health": card.get("u_health"), "attack": card.get("u_attack"), "speed": card.get("u_speed")}
        entity = entity_from_db(card, user_card_row)

        embed = discord.Embed(
            title=f"{card['name']}",
            description=card["description"] or "No description available.",
            color=RARITY_COLORS.get(card["rarity"], discord.Color.dark_gray())
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Quantity", value=str(card["quantity"]), inline=True)
        # Potential
        potential_val = int(card["potential"]) if card["potential"] is not None else 0
        embed.add_field(name="Potential", value=("⭐" * potential_val) if potential_val > 0 else "—", inline=True)
        # Stats (from entity for consistency)
        embed.add_field(name="Stats", value=str(entity.stats), inline=False)

        if card["image_url"]:
            embed.set_image(url=card["image_url"])

        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class InventoryView(View):
    def __init__(self, cards, balance, author):
        super().__init__(timeout=120)
        self.cards = cards  # rows with both card and user_card stat overrides
        self.balance = balance
        self.author = author
        self.current_rarity = "all"
        self.page = 0
        self.per_page = 10

        # Controls
        self.add_item(RaritySelect(self))
        self.card_select = None
        self.update_card_select()

        # Pagination buttons
        prev_button = Button(label="⬅️", style=discord.ButtonStyle.secondary)
        next_button = Button(label="➡️", style=discord.ButtonStyle.secondary)
        prev_button.callback = self.prev_page
        next_button.callback = self.next_page
        self.add_item(prev_button)
        self.add_item(next_button)

    def get_filtered_cards(self):
        if self.current_rarity == "all":
            return self.cards
        return [c for c in self.cards if c["rarity"] == self.current_rarity]

    def update_card_select(self):
        if self.card_select:
            self.remove_item(self.card_select)
        filtered = self.get_filtered_cards()
        if not filtered:
            filtered = [{
                "card_id": -1, "name": "No cards", "rarity": "none",
                "quantity": 0, "potential": 0, "description": "", "image_url": None,
                "health": None, "attack": None, "speed": None,
                "u_health": None, "u_attack": None, "u_speed": None,
                "base_name": "No cards"
            }]
        # Limit select options to current page slice to avoid mismatches
        start = self.page * self.per_page
        end = start + self.per_page
        chunk = filtered[start:end] or filtered[:self.per_page]
        self.card_select = CardSelect(self, chunk)
        self.add_item(self.card_select)

    def format_page(self):
        filtered = self.get_filtered_cards()
        start = self.page * self.per_page
        end = start + self.per_page
        chunk = filtered[start:end]

        embed = discord.Embed(
            title=f"🎴 {self.author.display_name}'s Inventory",
            description=f"💰 Bloodcoins: **{self.balance}**\nPage {self.page+1}/{max(1, (len(filtered)-1)//self.per_page+1)}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.author.display_avatar.url)

        for c in chunk:
            stats_preview = format_stats_inline(
                c,
                {"health": c.get("u_health"), "attack": c.get("u_attack"), "speed": c.get("u_speed")}
            )
            potential_val = int(c["potential"]) if c["potential"] is not None else 0
            embed.add_field(
                name=f"{c['base_name']} ({c['rarity'].capitalize()})",
                value=f"Qty: {c['quantity']} • {stats_preview}\nPotential: {('⭐' * potential_val) if potential_val > 0 else '—'}",
                inline=False
            )

        return embed

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_card_select()
            await interaction.response.edit_message(embed=self.format_page(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        filtered = self.get_filtered_cards()
        if self.page < (len(filtered)-1)//self.per_page:
            self.page += 1
            self.update_card_select()
            await interaction.response.edit_message(embed=self.format_page(), view=self)


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        """Show the user's inventory with rarity filter, card selector, pagination, and stats."""
        user_id = int(ctx.author.id)

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    c.card_id, c.base_name, c.name, c.rarity, c.potential, c.image_url, c.description,
                    c.health, c.attack, c.speed,
                    uc.quantity,
                    uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
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

        view = InventoryView(rows, balance, ctx.author)
        await ctx.send(embed=view.format_page(), view=view)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
