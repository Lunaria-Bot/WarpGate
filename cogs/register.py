import discord
from discord.ext import commands

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register")
    async def register(self, ctx):
        """Create a profile and give a random base card + 1000 BloodCoins."""
        user_id = int(ctx.author.id)
        username = str(ctx.author.display_name)

        async with self.bot.db.begin() as session:
            # Check if profile already exists
            exists = await session.scalar(
                "SELECT 1 FROM users WHERE user_id = :uid", {"uid": user_id}
            )
            if exists:
                await ctx.send(f"⚠️ {ctx.author.display_name}, you already have a profile.")
                return

            # Create profile with 1000 BloodCoins
            await session.execute("""
                INSERT INTO users (user_id, username, bloodcoins)
                VALUES (:uid, :uname, 1000)
            """, {"uid": user_id, "uname": username})

            # Select a random base card
            result = await session.execute(
                "SELECT id, character_name, form, image_url, description FROM cards WHERE form = 'base' ORDER BY random() LIMIT 1"
            )
            card = result.fetchone()
            if not card:
                await ctx.send("⚠️ No base cards available to assign.")
                return

            # Add card to inventory
            await session.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES (:uid, :cid, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, {"uid": user_id, "cid": card.id})

        # Confirmation embed
        embed = discord.Embed(
            title="✅ Profile Created!",
            description=f"A new profile has been created for **{ctx.author.display_name}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Starting Balance", value="1,000 BloodCoins", inline=True)
        embed.add_field(name="🎴 Starter Card", value=f"{card.character_name} (`{card.form}`)", inline=True)
        embed.set_thumbnail(url=card.image_url or ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Register(bot))
