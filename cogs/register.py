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
        discord_user = ctx.author
        discord_id = str(discord_user.id)
        username = str(discord_user.display_name)
        avatar_url = str(discord_user.display_avatar.url)
        discord_tag = f"{discord_user.name}#{discord_user.discriminator}"

        async with db_transaction(self.bot.db) as conn:
            exists = await conn.fetchval("SELECT 1 FROM players WHERE discord_id = $1", discord_id)
            if exists:
                await ctx.send(f"⚠️ {username}, you already have a profile.")
                return

            # Create player profile
            await conn.execute("""
                INSERT INTO players (
                    discord_id, name, discord_tag, bloodcoins, noblecoins, level, xp,
                    created_at, updated_at, avatar_url
                ) VALUES (
                    $1, $2, $3, 1000, 0, 1, 0, $4, $4, $5
                )
            """, discord_id, username, discord_tag, datetime.utcnow(), avatar_url)

            # Get internal user_id
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)

            # Get random starter card
            card = await conn.fetchrow("""
                SELECT id, character_name, form, image_url, series
                FROM cards
                WHERE form = 'base'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await ctx.send("⚠️ No base cards available. Please ask staff to add one.")
                return

            # Assign starter card
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, player_id, card["id"])

        embed = discord.Embed(
            title="✅ Profile Created!",
            description=f"A new profile has been created for **{username}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Starting Balance", value="1,000 BloodCoins", inline=True)
        embed.add_field(name="🎴 Starter Card", value=f"{card['character_name']} (`{card['form']}`)", inline=True)
        embed.add_field(name="📚 Series", value=card.get("series", "Unknown"), inline=True)
        embed.set_thumbnail(url=card["image_url"] or avatar_url)

        await ctx.send(embed=embed)

    @commands.command(name="sync_tags")
    @commands.is_owner()
    async def sync_tags(self, ctx):
        """Backfill discord_tag for all registered players."""
        async with db_transaction(self.bot.db) as conn:
            rows = await conn.fetch("SELECT discord_id FROM players WHERE discord_tag IS NULL")

            updated = 0
            for row in rows:
                member = ctx.guild.get_member(int(row["discord_id"]))
                if member:
                    discord_tag = f"{member.name}#{member.discriminator}"
                    await conn.execute(
                        "UPDATE players SET discord_tag = $1 WHERE discord_id = $2",
                        discord_tag, row["discord_id"]
                    )
                    updated += 1

        await ctx.send(f"✅ Synced {updated} discord tags.")

async def setup(bot):
    await bot.add_cog(Register(bot))
