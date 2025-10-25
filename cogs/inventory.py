import discord
from discord.ext import commands
from typing import Optional, List, Dict
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
    return (
        f"❤️ `{entity.stats.health}`  "
        f"🗡️ `{entity.stats.attack}`  "
        f"💨 `{entity.stats.speed}`"
    )

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
        super().__init__(placeholder="Filter by form…", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        self.parent_view.current_form = self.values[0]
        self.parent_view.page = 0
        self.parent_view.update_card_select()
        await interaction.response.edit_message(embed=self.parent_view.format_page(), view=self.parent_view)

class SortSelect(discord.ui.Select):
    def __init__(self, parent_view: "InventoryView"):
        options = [
            discord.SelectOption(label="By Level", value="level"),
            discord.SelectOption(label="By Quantity", value="quantity"),
            discord.SelectOption(label="By Name", value="name"),
        ]
        super().__init__(placeholder="Sort by…", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        self.parent_view.sort_mode = self.values[0]
        self.parent_view.page = 0
        self.parent_view.update_card_select()
        await interaction.response.edit_message(embed=self.parent_view.format_page(), view=self.parent_view)

class InventoryView(discord.ui.View):
    def __init__(self, cards: List[Dict], balance: int, author: discord.Member):
        super().__init__(timeout=120)
        self.cards = cards
        self.balance = balance
        self.author = author
        self.current_form = "all"
        self.sort_mode = "name"
        self.page = 0
        self.per_page = 10
        self.message: Optional[discord.Message] = None
        self.card_select: Optional[discord.ui.Select] = None
        self.filter_mode = False

        self.setup_main_view()

    def setup_main_view(self):
        self.clear_items()

        filter_button = discord.ui.Button(label="Filter", style=discord.ButtonStyle.primary)
        filter_button.callback = self.show_filters
        self.add_item(filter_button)

        prev_button = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        prev_button.callback = lambda i: self.change_page(i, -1)
        self.add_item(prev_button)

        next_button = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        next_button.callback = lambda i: self.change_page(i, +1)
        self.add_item(next_button)

        self.update_card_select()

    async def show_filters(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return

        self.clear_items()
        self.filter_mode = True

        self.add_item(FormSelect(self))
        self.add_item(SortSelect(self))

        back_button = discord.ui.Button(label="↩️ Back", style=discord.ButtonStyle.danger)
        back_button.callback = self.back_to_main
        self.add_item(back_button)

        await interaction.response.edit_message(embed=self.format_page(), view=self)

    async def back_to_main(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        self.filter_mode = False
        self.setup_main_view()
        await interaction.response.edit_message(embed=self.format_page(), view=self)

    def get_filtered_cards(self) -> List[Dict]:
        filtered = [c for c in self.cards if self.current_form == "all" or c["form"] == self.current_form]
        if self.sort_mode == "level":
            return sorted(filtered, key=lambda c: get_level(c.get("xp", 0)), reverse=True)
        elif self.sort_mode == "quantity":
            return sorted(filtered, key=lambda c: c["quantity"], reverse=True)
        return sorted(filtered, key=lambda c: c["character_name"])

    def update_card_select(self):
        if self.card_select:
            self.remove_item(self.card_select)
        filtered = self.get_filtered_cards()
        start, end = self.page * self.per_page, (self.page + 1) * self.per_page
        chunk = filtered[start:end]
        if not chunk:
            return
        options = []
        for c in chunk[:25]:
            entity = entity_from_db(c, {
                "health": c.get("u_health"),
                "attack": c.get("u_attack"),
                "speed": c.get("u_speed")
            })
            level = get_level(c.get("xp", 0))
            label = f"{c['character_name']} ({c['form'].capitalize()})"
            desc = f"Lvl {level} • Qty: {c['quantity']} • {format_stats(entity)}"
            options.append(discord.SelectOption(label=label, description=desc, value=str(c["card_id"])))
        self.card_select = discord.ui.Select(placeholder="Select a card…", options=options)
        self.card_select.callback = self.inspect_card
        self.add_item(self.card_select)

    async def inspect_card(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your inventory.", ephemeral=True)
            return
        card_id = int(self.card_select.values[0])
        card = next((c for c in self.cards if c["card_id"] == card_id), None)
        if not card:
            await interaction.response.send_message("⚠️ Card not found.", ephemeral=True)
            return
        entity = entity_from_db(card, {
            "health": card.get("u_health"),
            "attack": card.get("u_attack"),
            "speed": card.get("u_speed")
        })
        level = get_level(card.get("xp", 0))
        form = card.get("form") or "base"
        embed = discord.Embed(
            title=f"{FORM_EMOJIS.get(form, '')} {card['character_name']}",
            description=card["description"] or "No description available.",
            color=FORM_COLORS.get(form, discord.Color.dark_gray())
        )
        embed.add_field(name="Form", value=form.capitalize(), inline=True)
        embed.add_field(name="Level", value=f"{level} ({card.get('xp', 0)} XP)", inline=True)
        embed.add_field(name="Quantity", value=str(card["quantity"]), inline=True)
        embed.add_field(name="Stats", value=format_stats(entity), inline=False)
        if card["image_url"]:
            embed.set_image(url=card["image_url"])
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def format_page(self) -> discord.Embed:
        filtered = self.get_filtered_cards()
        start, end = self.page * self.per_page, (self.page + 1) * self.per_page
        chunk = filtered[start:end]

        total = len(filtered)
        awakened = sum(1 for c in filtered if c["form"] == "awakened")
        event = sum(1 for c in filtered if c["form"] == "event")

        embed = discord.Embed(
            title=f"🎴 {self.author.display_name}'s Inventory",
            description=(
                f"💰 Bloodcoins: **{self.balance:,}**\n"
                f"📄 Page {self.page+1}/{max(1, (len(filtered)-1)//self.per_page+1)}\n"
                f"📦 Total: **{total}** | ✨ {awakened} | 🎉 {event}"
            ),
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
            form = c.get("form") or "base"
            embed.add_field(
                name=f"{FORM_EMOJIS.get(form, '')} {c['character_name']} ({form.capitalize()})",
                value=f"Lvl {level} • Qty: **{c['quantity']}**\n{format_stats(entity)}",
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
                    c.id AS card_id, c.character_name, c.form, c.image_url, c.series,
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
