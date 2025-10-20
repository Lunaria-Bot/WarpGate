import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import random
import time
from models.card import Card
from models.user_card import UserCard
from utils.leveling import add_xp
from utils.db import db_transaction
from datetime import datetime

DRAW_ANIM = "https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif?ex=68f78cc0&is=68f63b40&hm=f37e1354814e7a4223fe46e2e06a6af88c23c4cc81f5329ed771374e81ade3ca&=&width=440&height=248"
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

class WarpDropView(View):
    def __init__(self, bot, user, card1, card2):
        super().__init__(timeout=20)
        self.bot = bot
        self.user = user
        self.card1 = card1
        self.card2 = card2
        self.claimed = False

        self.add_item(Button(label="Claim Left", style=discord.ButtonStyle.primary, custom_id="left"))
        self.add_item(Button(label="Claim Right", style=discord.ButtonStyle.primary, custom_id="right"))

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

        async with db_transaction(self.bot.db) as conn:
            await conn.execute("""
                INSERT INTO cards (character_name, form, image_url, description, created_at, code)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, card.character_name, card.form, card.image_url, card.description, card.created_at, card.code)

            card_id = await conn.fetchval("SELECT id FROM cards WHERE code = $1", card.code)

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, self.user.id, card_id)

            await conn.execute("UPDATE users SET bloodcoins = bloodcoins + 10 WHERE user_id = $1", self.user.id)

        await interaction.followup.send(
            f"✅ You claimed **{card.character_name}**!\nForm: `{card.form}`\nCode: `{card.code}`",
            ephemeral=True
        )

        await gain_buddy_xp(self.bot, self.user.id, amount=10)
        leveled_up, new_level = await add_xp(self.bot, self.user.id, 5)
        if leveled_up:
            await interaction.followup.send(f"🎉 You leveled up to **Level {new_level}**!", ephemeral=True)

    @discord.ui.button(label="Claim Left", style=discord.ButtonStyle.primary)
    async def claim_left(self, interaction: discord.Interaction, button: Button):
        await self.interaction_handler(interaction, self.card1)

    @discord.ui.button(label="Claim Right", style=discord.ButtonStyle.primary)
    async def claim_right(self, interaction: discord.Interaction, button: Button):
        await self.interaction_handler(interaction, self.card2)

async def gain_buddy_xp(bot, user_id: int, amount: int):
    async with db_transaction(bot.db) as conn:
        buddy_id = await conn.fetchval("SELECT buddy_card_id FROM users WHERE user_id = $1", user_id)
        if not buddy_id:
            return

        await conn.execute("""
            UPDATE user_cards
            SET xp = xp + $1,
                health = 100 + ((xp + $1) / 100)::int * 5,
                attack = 10 + ((xp + $1) / 100)::int * 2,
                speed = 10 + ((xp + $1) / 100)::int * 1
            WHERE user_id = $2 AND card_id = $3
        """, amount, user_id, buddy_id)

class Warp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.command(name="warp", aliases=["wd", "warpdrop"])
    async def warp(self, ctx):
        user_id = ctx.author.id
        now = int(time.time())

        if user_id in self.cooldowns and self.cooldowns[user_id] > now:
            ready_at = self.cooldowns[user_id]
            return await ctx.send(f"⏳ Time denies you once more... <t:{ready_at}:R>")

        cooldown_seconds = 600
        ready_at = now + cooldown_seconds
        self.cooldowns[user_id] = ready_at

        anim_embed = discord.Embed(description="🎴 Warping...", color=discord.Color.blurple())
        anim_embed.set_image(url=DRAW_ANIM)
        msg = await ctx.send(embed=anim_embed)
        await asyncio.sleep(2)

        async with db_transaction(self.bot.db) as conn:
            rows = await conn.fetch("""
                SELECT character_name, form, image_url, description
                FROM cards
                WHERE form = 'base'
                ORDER BY random()
                LIMIT 2
            """)
            if len(rows) < 2:
                await msg.edit(content="⚠️ Not enough cards available.", embed=None)
                return

        cards = []
        for row in rows:
            card = Card(
                character_name=row["character_name"],
                form=row["form"],
                image_url=row["image_url"],
                description=row["description"],
                created_at=datetime.utcnow()
            )
            card.code = card.generate_code()
            cards.append(card)

        embed = discord.Embed(
            title="🌌 Warp Drop",
            description="Choose one card to claim!",
            color=discord.Color.blurple()
        )
        embed.set_image(url=cards[0].image_url)
        embed.set_thumbnail(url=cards[1].image_url)

        view = WarpDropView(self.bot, ctx.author, cards[0], cards[1])
        view.message = msg
        await msg.edit(embed=embed, view=view)

        async def reminder():
            await asyncio.sleep(cooldown_seconds)
            await ctx.send(f"🔔 {ctx.author.mention} **Warp** is available again!")

        self.bot.loop.create_task(reminder())

    @commands.command(name="cooldown")
    async def cooldown(self, ctx):
        user_id = ctx.author.id
        now = int(time.time())
        tomorrow_midnight = (now // 86400 + 1) * 86400
        warp_ready = self.cooldowns.get(user_id, now)

        embed = discord.Embed(title="⏳ Cooldowns", color=discord.Color.blurple())
        embed.add_field(name="Daily", value=f"<t:{tomorrow_midnight}:R>", inline=False)
        embed.add_field(name="Warp", value=f"<t:{warp_ready}:R>", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Warp(bot))
