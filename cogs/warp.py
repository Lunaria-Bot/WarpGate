import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import random
import time
from models.card import Card
from models.user_card import UserCard
from utils.leveling import add_xp
from datetime import datetime

DRAW_ANIM = "https://yourcdn.com/animations/warp.gif"  # ton animation de warp
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
            await session.execute("""
                UPDATE users SET bloodcoins = bloodcoins + 10 WHERE user_id = :uid
            """, {"uid": interaction.user.id})
            await session.commit()

        await interaction.followup.send(
            f"✅ You claimed **{card.character_name}**!\nForm: `{card.form}`\nCode: `{card.code}`",
            ephemeral=True
        )

        # Gain buddy XP
        await gain_buddy_xp(self.bot, interaction.user.id, amount=10)

        # Gain player XP
        leveled_up, new_level = await add_xp(self.bot, interaction.user.id, 5)
        if leveled_up:
            await interaction.followup.send(f"🎉 You leveled up to **Level {new_level}**!", ephemeral=True)

async def gain_buddy_xp(bot, user_id: int, amount: int):
    async with bot.db.begin() as session:
        buddy_id = await session.scalar(
            "SELECT buddy_card_id FROM users WHERE user_id = :uid", {"uid": user_id}
        )
        if not buddy_id:
            return

        await session.execute("""
            UPDATE user_cards
            SET xp = xp + :amount,
                health = 100 + ((xp + :amount) / 100)::int * 5,
                attack = 10 + ((xp + :amount) / 100)::int * 2,
                speed = 10 + ((xp + :amount) / 100)::int * 1
            WHERE user_id = :uid AND card_id = :cid
        """, {"amount": amount, "uid": user_id, "cid": buddy_id})

class Warp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.command(name="warp", aliases=["wd", "warpdrop"])
    async def warp(self, ctx):
        user_id = ctx.author.id
        now = int(time.time())

        # Cooldown check
        if user_id in self.cooldowns and self.cooldowns[user_id] > now:
            ready_at = self.cooldowns[user_id]
            return await ctx.send(f"⏳ Time denies you once more... <t:{ready_at}:R>")

        cooldown_seconds = 600
        ready_at = now + cooldown_seconds
        self.cooldowns[user_id] = ready_at

        # Animation
        anim_embed = discord.Embed(description="🎴 Warping...", color=discord.Color.blurple())
        anim_embed.set_image(url=DRAW_ANIM)
        msg = await ctx.send(embed=anim_embed)
        await asyncio.sleep(2)

        # Draw 2 random base cards
        async with self.bot.db.begin() as session:
            result = await session.execute(
                "SELECT * FROM cards WHERE form = 'base' ORDER BY random() LIMIT 2"
            )
            rows = result.fetchall()
            if len(rows) < 2:
                await msg.edit(content="⚠️ Not enough cards available.", embed=None)
                return

            cards = []
            for row in rows:
                card = Card(
                    character_name=row.character_name,
                    form=row.form,
                    image_url=row.image_url,
                    description=row.description,
                    created_at=datetime.utcnow()
                )
                session.add(card)
                await session.flush()
                card.code = card.generate_code()
                cards.append(card)
            await session.commit()

        # Embed with both cards
        embed = discord.Embed(
            title="🌌 Warp Drop",
            description="Choose one card to claim!",
            color=discord.Color.blurple()
        )
        embed.set_image(url=cards[0].image_url)
        embed.set_thumbnail(url=cards[1].image_url)

        view = WarpDropView(self.bot, ctx.author, cards[0], cards[1])
        await msg.edit(embed=embed, view=view)

        # Reminder
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
