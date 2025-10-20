import random
import discord
from discord.ext import commands
from discord.ui import View, Button
from models.card import Card
from models.user_card import UserCard
from datetime import datetime

class WarpDropView(View):
    def __init__(self, bot, user, card1, card2):
        super().__init__(timeout=20)
        self.bot = bot
        self.user = user
        self.card1 = card1
        self.card2 = card2
        self.claimed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def claim_card(self, interaction: discord.Interaction, card):
        if self.claimed:
            await interaction.response.send_message("❌ You already claimed a card.", ephemeral=True)
            return

        self.claimed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        async with self.bot.db.begin() as session:
            session.add(card)
            await session.flush()
            card.code = card.generate_code()
            session.add(UserCard(user_id=interaction.user.id, card_id=card.id))
            await session.commit()

        await interaction.followup.send(f"✅ You claimed **{card.character_name}**!\nCode: `{card.code}`", ephemeral=True)

    @discord.ui.button(label="Claim Left", style=discord.ButtonStyle.primary)
    async def claim_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_card(interaction, self.card1)

    @discord.ui.button(label="Claim Right", style=discord.ButtonStyle.primary)
    async def claim_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_card(interaction, self.card2)


class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["wd", "warpdrop"])
    async def warpdrop(self, ctx):
        """Drop 2 random cards and let user choose one"""
        user = ctx.author
        characters = random.sample(["Laura Amou", "Akame", "Riven", "Kuro"], 2)

        cards = []
        async with self.bot.db.begin() as session:
            for name in characters:
                card = Card(
                    character_name=name,
                    form="base",
                    image_url=f"https://yourcdn.com/cards/{name.lower().replace(' ', '_')}_base.png",
                    description=f"{name} appears from the warp.",
                    created_at=datetime.utcnow()
                )
                session.add(card)
                await session.flush()
                card.code = card.generate_code()
                cards.append(card)
            await session.commit()

        embed = discord.Embed(title="🌌 Warp Drop", description="Choose one card to claim!", color=0x9b59b6)
        embed.set_image(url=cards[0].image_url)
        embed.set_thumbnail(url=cards[1].image_url)

        view = WarpDropView(self.bot, user, cards[0], cards[1])
        await ctx.send(embed=embed, view=view)

# Enregistrement du cog
async def setup(bot):
    await bot.add_cog(Cards(bot))
