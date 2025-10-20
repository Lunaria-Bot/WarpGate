import discord
from discord.ext import commands
from utils.db import db_transaction  # helper context manager

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register")
    async def register(self, ctx):
        """Create a profile and give a random base card + 1000 BloodCoins."""
        user_id = int(ctx.author.id)
        username = str(ctx.author.display_name)

        async with db_transaction(self.bot.db) as conn:
            exists = await conn.fetchval("SELECT 1 FROM users WHERE user_id = $1", user_id)
            if exists:
                await ctx.send(f"⚠️ {ctx.author.display_name}, you already have a profile.")
                return

            await conn.execute("""
                INSERT INTO users (user_id, username, bloodcoins)
                VALUES ($1, $2, 1000)
            """, user_id, username)

            card = await conn.fetchrow("""
                SELECT id, character_name, form, image_url, description
                FROM cards
                WHERE form = 'base'
                ORDER BY random()
                LIMIT 1
            """)

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, user_id, card["id"])

        embed = discord.Embed(
            title="✅ Profile Created!",
            description=f"A new profile has been created for **{ctx.author.display_name}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Starting Balance", value="1,000 BloodCoins", inline=True)
        embed.add_field(name="🎴 Starter Card", value=f"{card['character_name']} (`{card['form']}`)", inline=True)
        embed.set_thumbnail(url=card["image_url"] or ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Register(bot))
