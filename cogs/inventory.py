import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from typing import Optional
from .entities import entity_from_db, RARITY_BASE_STATS

# Shared rarity constants
RARITY_COLORS: dict[str, discord.Color] = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}
RARITY_ORDER = ["legendary", "epic", "rare", "common"]


def format_stats(entity) -> str:
    """Format stats from an Entity into a short inline string."""
    return f"❤️ {entity.stats.health} | 🗡️ {entity.stats.attack} | ⚡ {entity.stats.speed}"


class RaritySelect(Select):
    def __init__(self, parent_view: "InventoryView"):
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
        self.parent_view.page = 0
        self.parent_view.update_card_select()
        await interaction.response.edit_message(embed=self.parent_view.format_page(), view=self.parent_view)


class CardSelect(Select):
    def __init__(self, parent_view: "InventoryView", cards: list[dict]):
        self.parent_view = parent_view
        options = []
        for c in cards[:25]:
            entity = entity_from_db(c, {
                "health": c.get("u_health"),
                "attack": c.get("u_attack"),
                "speed": c.get("u_speed")
            })
            options.append(
                discord.SelectOption(
                    label=f"{c['name']} ({c['rarity'].capitalize()})",
                    description=f"Qty: {c['quantity']} • {format_stats(entity)}",
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

        entity = entity_from_db(card, {
            "health": card.get("u_health"),
            "attack": card.get("u_attack"),
            "speed": card.get("u_speed")
        })

        embed = discord.Embed(
            title=card["name"],
            description=card["description"] or "No description available.",
            color=RARITY_COLORS.get(card["rarity"], discord.Color.dark_gray())
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        embed.add_field(name="Quantity", value=str(card["quantity"]), inline=True)
        potential_val = int(card["potential"]) if card["potential"] else 0
        embed.add_field(name="Potential", value=("⭐" * potential_val) if potential_val > 0 else "—", inline=True)
        embed.add_field(name="Stats", value=format_stats(entity), inline=False)

        if card["image_url"]:
            embed.set_image(url=card["image_url"])

        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class InventoryView(View):
    def __init__(self, cards: list[dict], balance: int, author: discord.Member):
        super().__init__(timeout=120)
        self.cards = cards
        self.balance = balance
        self.author = author
        self.current_rarity = "all"
        self.page = 0
        self.per_page = 10
        self.message: Optional[discord.Message] = None

        self.add_item(RaritySelect(self))
        self.card_select: Optional[CardSelect] = None
        self.update_card_select()

        prev_button = Button(label="⬅️", style=discord.ButtonStyle.secondary)
        next_button = Button(label="➡️", style=discord.ButtonStyle.secondary)
        prev_button.callback = lambda i: self.change_page(i, -1)
        next_button.callback = lambda i: self.change_page(i, +1)
        self.add_item(prev_button)
        self.add_item(next_button)

    def get_filtered_cards(self) -> list[dict]:
        if self.current_rarity == "all":
            return self.cards
        return [c for c in self.cards if c["rarity"] == self.current_rarity]

    def update_card_select(self):
        if self.card_select:
            self.remove_item(self.card_select)
        filtered = self.get_filtered_cards()
        if not filtered:
            return
        start, end = self.page * self.per_page, (self.page + 1) * self.per_page
        chunk = filtered[start:end]
        self.card_select = CardSelect(self, chunk)
        self.add_item(self.card_select)

    def format_page(self) -> discord.Embed:
        filtered = self.get_filtered_cards()
        start, end = self.page * self.per_page, (self.page + 1) * self.per_page
        chunk = filtered[start:end]

        embed = discord.Embed(
            title=f"🎴 {self.author.display_name}'s Inventory",
            description=f"💰 Bloodcoins: **{self.balance}**\nPage {self.page+1}/{max(1, (len(filtered)-1)//self.per_page+1)}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.author.display_avatar.url)

        if not chunk:
            embed.add_field(name="Empty", value="📭 No cards to display.", inline=False)
            return embed

        for c in chunk:
            entity = entity_from_db(c, {
                "health": c.get("u_health"),
                "attack": c.get("u_attack"),
                "speed": c.get("u_speed")
            })
            potential_val = int(c["potential"]) if c["potential"] else 0
            embed.add_field(
                name=f"{c['base_name']} ({c['rarity'].capitalize()})",
                value=f"Qty: {c['quantity']} • {format_stats(entity)}\nPotential: {('⭐' * potential_val) if potential_val > 0 else '—'}",
                inline=False
            )
        return embed

    async def change_page(self, interaction: discord.Interaction, delta: int):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        filtered = self.get_filtered_cards()
        max_page = (len(filtered) - 1) // self.per_page
        new_page = self.page + delta
        if 0 <= new_page <= max_page:
            self.page = new_page
            self.update_card_select()
            await interaction.response.edit_message(embed=self.format_page(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx: commands.Context):
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

            balance = await conn.fetchval("SELECT bloodcoins FROM users WHERE user_id = $1", user_id)

            if not rows:
            await ctx.send("📭 Your inventory is empty. Use `!draw` to get cards!")
            return

        view = InventoryView(rows, balance, ctx.author)
        # keep a reference so on_timeout can disable controls
        message = await ctx.send(embed=view.format_page(), view=view)
        view.message = message


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
