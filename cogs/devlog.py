import discord
from discord.ext import commands

class DevLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="devlog1")
    @commands.has_permissions(administrator=True)
    async def devlog1(self, ctx):
        """Send Dev Log #1 announcement to the current channel."""
        content = (
            "**Hey @everyone!**\n\n"
            "> ## 🌌 Warp Gate — Dev Log #1\n"
            "> Today, we’re going to walk through how the game system works and what you can do once you join the world of **Warp Gate**.\n\n"
            "---\n\n"
            "### 💹 **Getting Started**\n"
            "> The bot prefix is: **`w`**\n"
            ">\n"
            "> Before anything, you must register using:  \n"
            "> ➤ **`wregister`**\n"
            ">\n"
            "> Once registered, you can draw your first card with:  \n"
            "> ➤ **`ww`** *(10-minute cooldown)*\n\n"
            "---\n\n"
            "### 📦 **Useful Commands**\n"
            "> 🧍 **`wp`** — See your profile  \n"
            "> 🃏 **`winv`** — View your current card collection\n\n"
            "---\n\n"
            "> That’s it for this first **Dev Log!**  \n"
            "> More features, NPCs, and secrets are coming soon… 👁️"
        )

        await ctx.send(content)

async def setup(bot):
    await bot.add_cog(DevLog(bot))
