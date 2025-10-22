import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import random
import time
import requests
from io import BytesIO
from models.card import Card
from utils.leveling import add_xp
from utils.db import db_transaction
from datetime import datetime

class WarpDropView(View):
    def __init__(self, bot, user, card1, card2):
        super().__init__(timeout=20)
        self.bot = bot
        self.user = user
        self.card1 = card1
        self.card2 = card2
        self.claimed = False
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def interaction_handler(self, interaction: discord.Interaction, card):
        if self.claimed:
            await interaction.response.send_message("❌ You already claimed a card.", ephemeral=True)
            return

        self.claimed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        discord_id = str(self.user.id)

        async with db_transaction(self.bot.db) as conn:
            await conn.execute("""
                INSERT INTO user_cards (discord_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (discord_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, discord_id, card.id)

            await conn.execute("UPDATE players SET bloodcoins = bloodcoins + 10 WHERE discord_id = $1", discord_id)

        await interaction.followup.send(
            f"✅ You claimed **{card.character_name}**!\nForm: `{card.form}`\nCode: `{card.code}`",
            ephemeral=True
        )

        await add_xp(self.bot, discord_id, 5)

    @discord.ui.button(label="1️⃣", style=discord.ButtonStyle.success)
    async def claim_one(self, interaction: discord.Interaction, button: Button):
        await self.interaction_handler(interaction, self.card1)

    @discord.ui.button(label="2️⃣", style=discord.ButtonStyle.success)
    async def claim_two(self, interaction: discord.Interaction, button: Button):
        await self.interaction_handler(interaction, self.card2)

class Warp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.command(name="warp", aliases=["w"])
    async def warp(self, ctx):
        discord_id = str(ctx.author.id)
        now = int(time.time())

        if discord_id in self.cooldowns and self.cooldowns[discord_id] > now:
            ready_at = self.cooldowns[discord_id]
            return await ctx.send(f"⏳ Time denies you once more... <t:{ready_at}:R>")

        cooldown_seconds = 600
        ready_at = now + cooldown_seconds
        self.cooldowns[discord_id] = ready_at

        async with db_transaction(self.bot.db) as conn:
            rows = await conn.fetch("""
                SELECT id, character_name, form, image_url
                FROM cards
                WHERE form = 'base' AND approved = TRUE
                ORDER BY random()
                LIMIT 2
            """)
            if len(rows) == 0:
                await ctx.send("⚠️ No approved base cards available.")
                return
            elif len(rows) == 1:
                rows.append(rows[0])

        cards = []
        for row in rows:
            card = Card(
                id=row["id"],
                character_name=row["character_name"],
                form=row["form"],
                image_url=row["image_url"],
                created_at=datetime.utcnow()
            )
            card.code = f"{row['character_name'][:12].replace(' ', '')}-{random.randint(1000,9999)}"
            cards.append(card)

        # Download images
        img1 = BytesIO(requests.get(cards[0].image_url).content)
        img2 = BytesIO(requests.get(cards[1].image_url).content)

        file1 = discord.File(img1, filename="card1.png")
        file2 = discord.File(img2, filename="card2.png")

        content = (
            f"🃏 {cards[0].character_name} — `{cards[0].code}`\n"
            f"🃏 {cards[1].character_name} — `{cards[1].code}`"
        )

        view = WarpDropView(self.bot, ctx.author, cards[0], cards[1])
        msg = await ctx.send(content=content, files=[file1, file2], view=view)
        view.message = msg

        async def reminder():
            await asyncio.sleep(cooldown_seconds)
            await ctx.send(f"🔔 {ctx.author.mention} **Warp** is available again!")

        self.bot.loop.create_task(reminder())

    @commands.command(name="cooldown", aliases=["cd"])
    async def cooldown(self, ctx):
        discord_id = str(ctx.author.id)
        now = int(time.time())
        tomorrow_midnight = (now // 86400 + 1) * 86400
        warp_ready = self.cooldowns.get(discord_id, now)

        embed = discord.Embed(title="⏳ Cooldowns", color=discord.Color.blurple())
        embed.add_field(name="Daily", value=f"<t:{tomorrow_midnight}:R>", inline=False)
        embed.add_field(name="Warp", value=f"<t:{warp_ready}:R>", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Warp(bot))
