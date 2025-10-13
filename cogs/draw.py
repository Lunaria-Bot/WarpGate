# cogs/draw.py
import discord
from discord.ext import commands
from db import tx, pool
from redis_client import redis
from rng import weighted_choice
import time

class DrawCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cd_sec = 600  # 10 minutes

    @commands.command(name="draw")
    async def draw(self, ctx: commands.Context):
        key = f"draw:cd:{ctx.author.id}"
        ttl = await redis.ttl(key)
        if ttl and ttl > 0:
            next_ts = int(time.time()) + ttl
            await ctx.send(f"Tu es en cooldown. Réessaie <t:{next_ts}:R>.")
            return

        async with tx() as conn:
            u = await conn.fetchrow("SELECT user_id FROM users WHERE user_id=$1", ctx.author.id)
            if not u:
                await ctx.send("Tu dois d’abord faire !register.")
                return

            cards = await conn.fetch("SELECT card_id, drop_weight FROM cards")
            if not cards:
                await ctx.send("Aucune carte configurée.")
                return

            choice = weighted_choice([(c["card_id"], c["drop_weight"]) for c in cards])

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, qty)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id) DO UPDATE SET qty = user_cards.qty + 1
            """, ctx.author.id, choice)

            await conn.execute("""
                UPDATE currencies SET blood_coins = blood_coins + 1, updated_at = NOW()
                WHERE user_id=$1
            """, ctx.author.id)

        await redis.set(key, "1", ex=self.cd_sec)

        async with pool().acquire() as conn:
            card = await conn.fetchrow("SELECT name, rarity FROM cards WHERE card_id=$1", choice)

        await ctx.send(f"Tu as obtenu: {card['name']} [{card['rarity']}]")

async def setup(bot):
    await bot.add_cog(DrawCog(bot))
