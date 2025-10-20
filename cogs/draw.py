import discord
from discord.ext import commands
import asyncio
import random
import time
from .entities import entity_from_db
from utils.leveling import add_xp

DRAW_ANIM = "https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif?ex=68f63b40&is=68f4e9c0&hm=1ac8ac005b79134db4e19dff962a32bad38b326d28aa8e230cf3941e019adf8e&=&width=440&height=248"

FORM_COLORS = {
    "base": discord.Color.blue(),
    "awakened": discord.Color.gold(),
    "event": discord.Color.magenta()
}
FORM_EMOJIS = {
    "base": "🟦",
    "awakened": "✨",
    "event": "🎉"
}

class Warp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    async def gain_buddy_xp(self, user_id: int, amount: int):
        async with self.bot.db.begin() as session:
            buddy_id = await session.scalar(
                "SELECT buddy_card_id FROM users WHERE user_id = $1", user_id
            )
            if not buddy_id:
                return

            await session.execute("""
                UPDATE user_cards
                SET xp = xp + $1,
                    health = 100 + ((xp + $1) / 100)::int * 5,
                    attack = 10 + ((xp + $1) / 100)::int * 2,
                    speed = 10 + ((xp + $1) / 100)::int * 1
                WHERE user_id = $2 AND card_id = $3
            """, amount, user_id, buddy_id)

    @commands.command(name="warp")
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

        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT *
                FROM cards
                WHERE form = 'base'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await msg.edit(content="⚠️ No base cards available.", attachments=[], embed=None)
                return

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, user_id, card["id"])

            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10
                WHERE user_id = $1
            """, user_id)

        await self.gain_buddy_xp(user_id, amount=10)

        entity = entity_from_db(card)
        level = card.get("xp", 0) // 100 + 1

        result_embed = discord.Embed(
            title=f"{FORM_EMOJIS.get(card['form'], '')} You got: {card['character_name']}",
            description=card["description"] or "No description available.",
            color=FORM_COLORS.get(card["form"], discord.Color.dark_gray())
        )
        result_embed.add_field(name="Form", value=card["form"].capitalize(), inline=True)
        result_embed.add_field(name="Level", value=f"{level} XP", inline=True)
        result_embed.add_field(
            name="Stats",
            value=f"❤️ {entity.stats.health} | 🗡️ {entity.stats.attack} | 💨 {entity.stats.speed}",
            inline=False
        )
        if card["image_url"]:
            result_embed.set_image(url=card["image_url"])

        await msg.edit(content=None, attachments=[], embed=result_embed)

        leveled_up, new_level = await add_xp(self.bot, user_id, 5)
        if leveled_up:
            await ctx.send(f"🎉 {ctx.author.mention} leveled up to **Level {new_level}**!")

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
