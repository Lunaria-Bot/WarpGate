import discord
from discord.ext import commands
from utils.db import db_transaction
from datetime import datetime

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register")
    async def register(self, ctx):
        """Create a profile and give a random base card + 1000 BloodCoins."""
        discord_id = str(ctx.author.id)
        username = str(ctx.author.display_name)
        avatar_url = str(ctx.author.display_avatar.url)

        async with db_transaction(self.bot.db) as conn:
            exists = await conn.fetchval("SELECT 1 FROM players WHERE discord_id = $1", discord_id)
            if exists:
                await ctx.send(f"⚠️ {ctx.author.display_name}, you already have a profile.")
                return

            await conn.execute("""
                INSERT INTO players (
                    discord_id, name, bloodcoins, noblecoins, level, xp, created_at, updated_at, avatar_url
                ) VALUES (
                    $1, $2, 1000, 0, 1, 0, $3, $3, $4
                )
            """, discord_id, username, datetime.utcnow(), avatar_url)

            card = await conn.fetchrow("""
                SELECT id, character_name, form, image_url, description
                FROM cards
                WHERE form = 'base'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await ctx.send("⚠️ No base cards available. Please ask staff to add one.")
                return

            await conn.execute("""
                INSERT INTO user_cards (discord_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (discord_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, discord_id, card["id"])

        embed = discord.Embed(
            title="✅ Profile Created!",
            description=f"A new profile has been created for **{ctx.author.display_name}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Starting Balance", value="1,000 BloodCoins", inline=True)
        embed.add_field(name="🎴 Starter Card", value=f"{card['character_name']} (`{card['form']}`)", inline=True)
        embed.set_thumbnail(url=card["image_url"] or avatar_url)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Register(bot))
