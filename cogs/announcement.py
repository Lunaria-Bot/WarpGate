import discord
from discord import app_commands
from discord.ext import commands

# Role ID allowed to use announcements
ALLOWED_ROLE_ID = 1414571208829304913

class Announcement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_permission(self, interaction: discord.Interaction) -> bool:
        return any(r.id == ALLOWED_ROLE_ID for r in interaction.user.roles)

    @app_commands.command(name="announce", description="Send an announcement embed")
    @app_commands.guilds(discord.Object(id=1399784437440319508))  # restrict to your guild
    async def announce(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        image_url: str | None = None
    ):
        """Slash command to send an announcement embed."""
        if not self.has_permission(interaction):
            await interaction.response.send_message("⚠️ You don’t have permission to use this command.", ephemeral=True)
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple()
        )
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else discord.Embed.Empty
        )
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"Announcement by {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="announce_faq", description="Send a FAQ-style announcement with multiple fields")
    @app_commands.guilds(discord.Object(id=1399784437440319508))
    async def announce_faq(
        self,
        interaction: discord.Interaction,
        title: str,
        intro: str
    ):
        """Slash command to send a FAQ-style announcement embed with fields."""
        if not self.has_permission(interaction):
            await interaction.response.send_message("⚠️ You don’t have permission to use this command.", ephemeral=True)
            return

        embed = discord.Embed(
            title=title,
            description=intro,
            color=discord.Color.gold()
        )
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else discord.Embed.Empty
        )

        # Example fields (customize as needed)
        embed.add_field(name="📌 Useful Commands", value="`/daily`, `/stats`, `/cards`, `/packs`, `/inventory`, `/shop`", inline=False)
        embed.add_field(name="❓ FAQ", value="Cards and stats are generated after registering.\nUse `/daily` for free packs.", inline=False)
        embed.add_field(name="💎 Premium", value="Premium gives more packs, inventory, and card limits.", inline=False)
        embed.add_field(name="🏰 Clans", value="Create or join clans with `/createclan`, `/joinclan`, `/clanstats`.", inline=False)

        embed.set_footer(text=f"Announcement by {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Announcement(bot))
