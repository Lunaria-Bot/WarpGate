import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import random
import time
import requests
from io import BytesIO
from PIL import Image
from models.card import Card
from utils.leveling import add_xp
from utils.db import db_transaction
from datetime import datetime

def render_combined_image(card1, card2, max_size=(300, 300), spacing=24):
    try:
        img1 = Image.open(BytesIO(requests.get(card1.image_url, timeout=5).content)).convert("RGBA")
        img2 = Image.open(BytesIO(requests.get(card2.image_url, timeout=5).content)).convert("RGBA")

        img1.thumbnail(max_size, Image.LANCZOS)
        img2.thumbnail(max_size, Image.LANCZOS)

        height = max(img1.height, img2.height)
        total_width = img1.width + img2.width + spacing

        combined = Image.new("RGBA", (total_width, height), (0, 0, 0, 0))
        combined.paste(img1, (0, 0))
        combined.paste(img2, (img1.width + spacing, 0))

        buffer = BytesIO()
        combined.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"❌ Failed to render combined image: {e}")
        fallback = Image.new("RGBA", (max_size[0]*2 + spacing, max_size[1]), (30, 30, 30, 255))
        buffer = BytesIO()
        fallback.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

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
            await self.message.edit(view=None)
            if not self.claimed:
                await self.message.channel.send("😢 Oh no, you let them ran away!")

    async def interaction_handler(self, interaction: discord.Interaction, card):
        if self.claimed:
            await interaction.response.send_message("❌ You already claimed a card.", ephemeral=True)
            return

        self.claimed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=None)

        discord_id = int(self.user.id)

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                await interaction.followup.send("⚠️ You don't have a profile yet. Use `wregister`.", ephemeral=True)
                return

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, player_id, card.id)

            await conn.execute("UPDATE players SET bloodcoins = bloodcoins + 10 WHERE id = $1", player_id)

        await interaction.followup.send(
            f"✅ You claimed **{card.character_name}**!\nForm: `{card.form}`",
            ephemeral=True
        )

        await interaction.channel.send(f"🎉 {interaction.user.mention} just claimed **{card.character_name}**!")
        await add_xp(self.bot, discord_id, 5)

    @discord.ui.button(label="Claim 1", style=discord.ButtonStyle.primary, row=0)
    async def claim_one(self, interaction: discord.Interaction, button: Button):
        await self.interaction_handler(interaction, self.card1)

    @discord.ui.button(label="Claim 2", style=discord.ButtonStyle.primary, row=0)
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
                SELECT id, character_name, form, image_url, series
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
                series=row["series"],
                created_at=datetime.utcnow()
            )
            cards.append(card)

        combined = render_combined_image(cards[0], cards[1])
        file = discord.File(combined, filename="drop.png")

        lines = [
            f":one: **{cards[0].character_name}** — *{cards[0].series or 'Unknown'}*",
            f":two: **{cards[1].character_name}** — *{cards[1].series or 'Unknown'}*"
        ]
        intro = "Here are the warped cards:\n" + "\n".join(lines)

        view = WarpDropView(self.bot, ctx.author, cards[0], cards[1])
        msg = await ctx.send(content=intro, file=file, view=view)
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
