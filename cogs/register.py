import discord
from discord.ext import commands

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register")
    async def register(self, ctx):
        """Create a profile for the user if it doesn't exist yet."""
        user_id = int(ctx.author.id)  # ✅ force int
        username = str(ctx.author.display_name)

        async with self.bot.db.acquire() as conn:
            # Check if profile already exists
            exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE user_id = $1", user_id
            )

            if exists:
                await ctx.send(f"⚠️ {ctx.author.display_name}, you already have a profile.")
                return

            # Insert new profile with username + balance
            await conn.execute("""
                INSERT INTO users (user_id, username, bloodcoins)
                VALUES ($1, $2, 0)
            """, user_id, username)

        embed = discord.Embed(
            title="✅ Profile Created!",
            description=f"A new profile has been created for **{ctx.author.display_name}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Starting Balance", value="0 BloodCoins", inline=True)
        embed.add_field(name="📅 Created", value="Now", inline=True)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Register(bot))
