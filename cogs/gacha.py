import discord
from discord.ext import commands
from utils.db import db_transaction
import random

PULL_RATES = {
    "base": 0.90,
    "awakened": 0.095,
    "event": 0.005
}

FORM_ANIMATIONS = {
    "base": "https://your.cdn.com/animations/base.gif",
    "awakened": "https://your.cdn.com/animations/awakened.gif",
    "event": "https://your.cdn.com/animations/event.gif"
}

class GachaView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author

    @discord.ui.button(label="Summon 1 Gate Key", style=discord.ButtonStyle.primary)
    async def summon_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your summon.", ephemeral=True)
            return

        await self.handle_summon(interaction, count=1)

    @discord.ui.button(label="Multi-Summon 10 Gate Keys", style=discord.ButtonStyle.success)
    async def summon_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ This is not your summon.", ephemeral=True)
            return

        await self.handle_summon(interaction, count=10)

    async def handle_summon(self, interaction: discord.Interaction, count: int):
        discord_id = str(self.author.id)

        async with db_transaction(interaction.client.db) as conn:
            player = await conn.fetchrow("SELECT id, gate_keys, pulls FROM players WHERE discord_id = $1", discord_id)
            if not player:
                await interaction.response.send_message("⚠️ You don't have a profile.", ephemeral=True)
                return

            if player["gate_keys"] < count:
                await interaction.response.send_message("🔒 Not enough Gate Keys.", ephemeral=True)
                return

            pulls = []
            guaranteed_awakened = False
            guaranteed_event = player["pulls"] + count >= 50

            for i in range(count):
                form = self.roll_form(guaranteed_event if i == count - 1 else False)
                if form == "awakened":
                    guaranteed_awakened = True
                pulls.append(form)

            # Guarantee one awakened if multi-summon
            if count == 10 and not guaranteed_awakened:
                pulls[random.randint(0, 9)] = "awakened"

            # Deduct keys and update pity
            await conn.execute("""
                UPDATE players SET gate_keys = gate_keys - $1, pulls = CASE WHEN pulls + $1 >= 50 THEN 0 ELSE pulls + $1 END
                WHERE discord_id = $2
            """, count, discord_id)

            cards = []
            for form in pulls:
                card = await conn.fetchrow("""
                    SELECT id, character_name, image_url, description
                    FROM cards
                    WHERE form = $1
                    ORDER BY random()
                    LIMIT 1
                """, form)

                if card:
                    await conn.execute("""
                        INSERT INTO user_cards (user_id, card_id, quantity)
                        VALUES ($1, $2, 1)
                        ON CONFLICT (user_id, card_id)
                        DO UPDATE SET quantity = user_cards.quantity + 1
                    """, player["id"], card["id"])
                    cards.append((form, card))

        # Build embed
        embed = discord.Embed(
            title=f"🔮 {self.author.display_name}'s Summon",
            description=f"✨ You used {count} Gate Key{'s' if count > 1 else ''}!",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=self.author.display_avatar.url)

        for form, card in cards:
            embed.add_field(
                name=f"{card['character_name']} ({form.capitalize()})",
                value=card["description"] or "No description available.",
                inline=False
            )

        embed.set_image(url=FORM_ANIMATIONS.get(cards[-1][0], ""))  # Show animation for last pull
        await interaction.response.edit_message(embed=embed, view=self)

    def roll_form(self, force_event=False) -> str:
        if force_event:
            return "event"
        roll = random.random()
        if roll < PULL_RATES["event"]:
            return "event"
        elif roll < PULL_RATES["event"] + PULL_RATES["awakened"]:
            return "awakened"
        return "base"

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="summon")
    async def summon(self, ctx):
        view = GachaView(ctx.author)
        embed = discord.Embed(
            title="🚪 Warp Gate Summon",
            description="Use your Gate Keys to summon powerful cards!",
            color=discord.Color.blurple()
        )
        embed.set_image(url="https://your.cdn.com/animations/gate_idle.gif")
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Gacha(bot))
