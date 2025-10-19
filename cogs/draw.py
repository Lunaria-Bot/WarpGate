import discord
from discord.ext import commands
import asyncio
import random
import time
from .entities import entity_from_db, Entity
from utils.leveling import add_xp  # XP helper

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

RARITY_EMOJIS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡"
}

MIMIC_QUOTES = [
    "Treasure? Oh no, I’m the real reward.",
    "Curiosity tastes almost as good as fear.",
    "Funny how you never suspect the things you want most."
]

MIMIC_IMAGE = "https://media.discordapp.net/attachments/1428401795364814948/1428401824024756316/image.png"
DRAW_ANIM = "https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif?ex=68f63b40&is=68f4e9c0&hm=1ac8ac005b79134db4e19dff962a32bad38b326d28aa8e230cf3941e019adf8e&=&width=440&height=248"

# --- Helper: update quest progress ---
async def update_quest_progress(conn, user_id: int, quest_desc: str, amount: int = 1):
    await conn.execute("""
        UPDATE user_quests uq
        SET progress = progress + $3,
            completed = (progress + $3) >= qt.target
        FROM quest_templates qt
        WHERE uq.quest_id = qt.quest_id
          AND uq.user_id = $1
          AND qt.description = $2
          AND uq.claimed = FALSE
    """, user_id, quest_desc, amount)


class Warp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}  # {user_id: unix_timestamp_ready}

    @commands.command(name="warp")
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

        # --- Check player level ---
        async with self.bot.db.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT level FROM users WHERE user_id = $1", user_id
            )
        player_level = user_row["level"] if user_row else 1

        # --- Mimic encounter (10%) only if level >= 5 ---
        if player_level >= 5 and random.randint(1, 100) <= 10:
            # ... (tout le code du combat Mimic que tu avais déjà) ...
            # et return à la fin
            return

        # --- Normal warp (tirage classique) ---
        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT *
                FROM cards
                WHERE rarity = 'common'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await msg.edit(content="⚠️ No common cards available.", attachments=[], embed=None)
                return

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, user_id, card["card_id"])

            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10
                WHERE user_id = $1
            """, user_id)

            await update_quest_progress(conn, user_id, "Draw 5 times", 1)
            await update_quest_progress(conn, user_id, "Draw 10 times", 1)
            await update_quest_progress(conn, user_id, "Draw 100 times", 1)

        rarity = card["rarity"]
        potential_val = int(card["potential"]) if card["potential"] else 0
        entity = entity_from_db(card)

        result_embed = discord.Embed(
            title=f"You just got: {card['name']}",
            color=RARITY_COLORS.get(rarity, discord.Color.dark_gray())
        )
        result_embed.add_field(name="Rarity", value=rarity.capitalize(), inline=True)
        result_embed.add_field(
            name="Potential",
            value=("⭐" * potential_val) if potential_val > 0 else "—",
            inline=True
        )
        result_embed.add_field(
            name="Stats",
            value=f"❤️ {entity.stats.health} | 🗡️ {entity.stats.attack} | ⚡ {entity.stats.speed}",
            inline=False
        )
        if card["image_url"]:
            result_embed.set_image(url=card["image_url"])

        await msg.edit(content=None, attachments=[], embed=result_embed)

        # XP gain
        leveled_up, new_level = await add_xp(self.bot, user_id, 5)
        if leveled_up:
            await ctx.send(f"🎉 {ctx.author.mention} leveled up to **Level {new_level}**!")

        # Automatic reminder
        async def reminder():
            await asyncio.sleep(cooldown_seconds)
            await ctx.send(f"🔔 {ctx.author.mention} **Warp** is available again !")

        self.bot.loop.create_task(reminder())

    @warp.error
    async def warp_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = int(error.retry_after // 60)
            seconds = int(error.retry_after % 60)
            await ctx.send(
                f"⏳ You need to wait **{minutes}m {seconds}s** before using `!warp` again!",
                delete_after=10
            )
        else:
            await ctx.send("⚠️ An unexpected error occurred while processing your warp.", delete_after=10)

    @commands.command(name="cooldown")
    async def cooldown(self, ctx):
        user_id = ctx.author.id
        now = int(time.time())

        # Daily reset à minuit UTC
        tomorrow_midnight = (now // 86400 + 1) * 86400
        daily_ready = tomorrow_midnight

        # Warp basé sur cooldown dict
        warp_ready = self.cooldowns.get(user_id, now)

        embed = discord.Embed(title="⏳ Cooldowns", color=discord.Color.blurple())
        embed.add_field(name="Daily", value=f"<t:{daily_ready}:R>", inline=False)
        embed.add_field(name="Warp", value=f"<t:{warp_ready}:R>", inline=False)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Warp(bot))
