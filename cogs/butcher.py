import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import random

# --- Butcher Quotes ---
BUTCHER_QUOTES = [
    "Some cuts take a little more patience… but they’re worth it in the end.",
    "Takes a steady hand to separate what stays… and what goes.",
    "There’s beauty in precision. Clean lines, clean conscience.",
    "Still set two plates out, every night. Habit’s hard to kill.",
    "She used to hum while I worked... Now the silence screams at me.",
    "Sometimes, I lay her apron on the table... and pretend she’s just out back, sharpening the knives.",
    "She used to call me gentle. I am gentle where it matters.",
    "The ledger says 'customers.' My heart says different.",
    "I set a place for her every night. Sometimes another sits too.",
    "I catalog everything. Some people make excellent additions."
]

# --- Conversion Values ---
BURN_VALUES = {
    "common": 50,
    "rare": 100,
    "epic": 1000,
    "legendary": 10000
}

BUTCHER_IMAGE = "https://media.discordapp.net/attachments/1428075046454431784/1428088206192279666/image.png?format=webp&quality=lossless&width=1027&height=575"

# --- Modal for quantity input ---
class QuantityModal(Modal, title="Butcher"):
    quantity = TextInput(
        label="Quantity to butcher",
        placeholder="Enter a number",
        required=True
    )

    def __init__(self, bot, card, value):
        super().__init__()
        self.bot = bot
        self.card = card
        self.value = value

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.quantity.value)
        except ValueError:
            await interaction.response.send_message("⚠️ Invalid number.", ephemeral=True)
            return

        if qty <= 0 or qty > self.card["quantity"]:
            await interaction.response.send_message("⚠️ Invalid quantity.", ephemeral=True)
            return

        total_value = self.value * qty

        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE user_cards
                SET quantity = quantity - $1
                WHERE user_id = $2 AND card_id = $3 AND quantity >= $1
            """, qty, interaction.user.id, self.card["card_id"])
            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + $1
                WHERE user_id = $2
            """, total_value, interaction.user.id)

        await interaction.response.send_message(
            f"🔪 You butchered **{qty}x {self.card['name']} ({self.card['rarity'].capitalize()})** "
            f"and earned 💰 {total_value} Bloodcoins.",
            ephemeral=True
        )

# --- Main View ---
class ButcherView(View):
    def __init__(self, bot, author):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author

        value_btn = Button(label="📖 Value", style=discord.ButtonStyle.primary)
        butcher_btn = Button(label="🔪 Butchering", style=discord.ButtonStyle.danger)
        leave_btn = Button(label="🚪 Leave the shop", style=discord.ButtonStyle.secondary)

        value_btn.callback = self.show_value
        butcher_btn.callback = self.show_butchering
        leave_btn.callback = self.leave_shop

        self.add_item(value_btn)
        self.add_item(butcher_btn)
        self.add_item(leave_btn)

    async def show_value(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This menu is not for you.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📖 Conversion Values",
            description="\n".join([f"**1 {r.capitalize()}** = 💰 {v} Bloodcoins" for r, v in BURN_VALUES.items()]),
            color=discord.Color.red()
        )
        embed.set_image(url=BUTCHER_IMAGE)
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_butchering(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This menu is not for you.", ephemeral=True)
            return

        async with self.bot.db.acquire() as conn:
            cards = await conn.fetch("""
                SELECT uc.card_id, uc.quantity, c.name, c.rarity
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1 AND uc.quantity > 0
            """, interaction.user.id)

        if not cards:
            await interaction.response.send_message("⚠️ You have no cards to butcher.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=f"{c['name']} ({c['rarity'].capitalize()}) x{c['quantity']}",
                value=str(c['card_id'])
            )
            for c in cards
        ]

        select = Select(placeholder="Choose a card to butcher", options=options, min_values=1, max_values=1)

        async def select_callback(inter: discord.Interaction):
            card_id = int(select.values[0])
            card = next(c for c in cards if c["card_id"] == card_id)
            value = BURN_VALUES.get(card["rarity"], 0)

            await inter.response.send_modal(QuantityModal(self.bot, card, value))

        select.callback = select_callback
        view = View()
        view.add_item(select)

        embed = discord.Embed(
            title="🔪 Butchering",
            description="Choose a card and enter how many copies you want to butcher.",
            color=discord.Color.dark_red()
        )
        embed.set_image(url=BUTCHER_IMAGE)
        await interaction.response.edit_message(embed=embed, view=view)

    async def leave_shop(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This menu is not for you.", ephemeral=True)
            return

        quote = random.choice(BUTCHER_QUOTES)
        embed = discord.Embed(
            title="🥩 The Butcher",
            description=f"_{quote}_\n\nWelcome back, {interaction.user.display_name}...",
            color=discord.Color.dark_red()
        )
        embed.set_image(url=BUTCHER_IMAGE)
        await interaction.response.edit_message(embed=embed, view=self)

# --- Cog ---
class Butcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="butcher")
    async def butcher(self, ctx):
        """Open the Butcher NPC menu."""
        quote = random.choice(BUTCHER_QUOTES)
        embed = discord.Embed(
            title="🥩 The Butcher",
            description=f"_{quote}_\n\nWelcome, {ctx.author.display_name}...",
            color=discord.Color.dark_red()
        )
        embed.set_image(url=BUTCHER_IMAGE)

        view = ButcherView(self.bot, ctx.author)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Butcher(bot))
