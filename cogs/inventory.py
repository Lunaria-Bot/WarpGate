import discord
from discord.ext import commands
from typing import Optional
from .entities import entity_from_db
from utils.db import db_transaction

FORM_EMOJIS = {
    "base": "🟦",
    "awakened": "✨",
    "event": "🎉"
}
FORM_COLORS = {
    "base": discord.Color.blue(),
    "awakened": discord.Color.gold(),
    "event": discord.Color.magenta()
}

def format_stats(entity) -> str:
    return f"❤️ {entity.stats.health} | 🗡️ {entity.stats.attack} | 💨 {entity.stats.speed}"

def get_level(xp: int) -> int:
    return xp // 100 + 1

class FormSelect(discord.ui.Select):
    def __init__(self, parent_view: "InventoryView"):
        options = [
            discord.SelectOption(label="All", value="all"),
            discord.SelectOption(label="Base 🟦", value="base"),
            discord.SelectOption(label="Awakened ✨", value="awakened"),
            discord.SelectOption(label="Event 🎉", value="event"),
        ]
        super().__init__(placeholder="Filter by form…", options=options, min_values=1, max_values=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return

        self.parent_view.current_form = self.values[0]
        self.parent_view.page = 0
        self.parent_view.update_card_select()
        await interaction.response.edit_message(embed=self.parent_view.format_page(), view=self.parent_view)

class CardSelect(discord.ui.Select):
    def __init__(self, parent_view: "InventoryView", cards: list[dict]):
        self.parent_view = parent_view
        options = []
        for c in cards[:25]:
            entity = entity_from_db(c, {
                "health": c.get("u_health"),
                "attack": c.get("u_attack"),
                "speed": c.get("u_speed")
            })
            level = get_level(c.get("xp", 0))
            options.append(
                discord.SelectOption(
                    label=f"{c['character_name']} ({c['form'].capitalize()})",
                    description=f"Lvl {level} • Qty: {c['quantity']} • {format_stats(entity)}",
                    value=str(c['card_id'])
                )
            )
        super().__init__(placeholder="Select a card…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return

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

        level = get_level(card.get("xp", 0))
        embed = discord.Embed(
            title=f"{FORM_EMOJIS.get(card['form'], '')} {card['character_name']}",
            description=card["description"] or "No description available.",
            color=FORM_COLORS.get(card["form"], discord.Color.dark_gray())
        )
        embed.add_field(name="Form", value=card["form"].capitalize(), inline=True)
        embed.add_field(name="Level", value=f"{level} ({card.get('xp', 0)} XP)", inline=True)
        embed.add_field(name="Quantity", value=str(card["quantity"]), inline=True)
        embed.add_field(name="Stats", value=format_stats(entity), inline=False)

        if card["image_url"]:
            embed.set_image(url=card["image_url"])

        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class InventoryView(discord.ui.View):
    def __init__(self, cards: list[dict], balance: int, author: discord.Member):
        super().__init__(timeout=120)
        self.cards = cards
        self.balance = balance
        self.author = author
        self.current_form = "all"
        self.page = 0
        self.per_page = 10
        self.message: Optional[discord.Message] = None

        self.add_item(FormSelect(self))
        self.card_select: Optional[CardSelect] = None
        self.update_card_select()

        prev_button = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        next_button = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        prev_button.callback = lambda i: self.change_page(i, -1)
        next_button.callback = lambda i: self.change_page(i, +1)
        self.add_item(prev_button)
        self.add_item(next_button)

    def get_filtered_cards(self) -> list[dict]:
        if self.current_form == "all":
            return self.cards
        return [c for c in self.cards if c["form"] == self.current_form]

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
            description=f"💰 Bloodcoins: **{self.balance:,}**\n📄 Page {self.page+1}/{max(1, (len(filtered)-1)//self.per_page+1)}",
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
            level = get_level(c.get("xp", 0))
            embed.add_field(
                name=f"{FORM_EMOJIS.get(c['form'], '')} {c['character_name']} ({c['form'].capitalize()})",
                value=(
                    f"Lvl {level} • Qty: **{c['quantity']}**\n"
                    f"{format_stats(entity)}"
                ),
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
    async def inventory(self, ctx, member: Optional[discord.Member] = None):
        user = member or ctx.author
        discord_id = str(user.id)

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                await ctx.send("⚠️ You don't have a profile yet. Use `wregister` to create one.")
                return

            rows = await conn.fetch("""
                SELECT
                    c.id AS card_id, c.character_name, c.form, c.image_url, c.description,
                    uc.quantity, uc.xp,
                    uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                FROM user_cards uc
                JOIN cards c ON c.id = uc.card_id
                WHERE uc.user_id = $1
                ORDER BY 
                    CASE c.form
                        WHEN 'awakened' THEN 1
                        WHEN 'event' THEN 2
                        ELSE 3
                    END,
                    c.character_name
            """, player_id)

            balance = await conn.fetchval("SELECT bloodcoins FROM players WHERE discord_id = $1", discord_id)

        if not rows:
            await ctx.send("📭 Your inventory is empty. Use `ww` to get cards!")
            return

        view = InventoryView(rows, balance, user)
        message = await ctx.send(embed=view.format_page(), view=view)
        view.message = message

async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
