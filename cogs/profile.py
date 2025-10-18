import discord
from discord import app_commands
from discord.ext import commands

RARITY_EMOJIS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡"
}

GUILD_ID = 1399784437440319508  # your guild ID


class ProfileView(discord.ui.View):
    def __init__(self, user: discord.Member, bot: commands.Bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot

    @discord.ui.button(label="📦 Inventory", style=discord.ButtonStyle.primary)
    async def inventory_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ This is not your profile.", ephemeral=True)
            return
        cog = self.bot.get_cog("Inventory")
        if cog:
            await cog.show_inventory(interaction, self.user)
        else:
            await interaction.response.send_message("⚠️ Inventory system not loaded.", ephemeral=True)

    @discord.ui.button(label="📜 Quests", style=discord.ButtonStyle.secondary)
    async def quests_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ This is not your profile.", ephemeral=True)
            return
        cog = self.bot.get_cog("Quests")
        if cog:
            await cog.show_quests(interaction, self.user)
        else:
            await interaction.response.send_message("⚠️ Quest system not loaded.", ephemeral=True)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.success)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ This is not your profile.", ephemeral=True)
            return

        async with self.bot.db.acquire() as conn:
            totals = await conn.fetchrow("""
                SELECT 
                    COALESCE(SUM(c.health * uc.quantity), 0) AS total_health,
                    COALESCE(SUM(c.attack * uc.quantity), 0) AS total_attack,
                    COALESCE(SUM(c.speed * uc.quantity), 0) AS total_speed
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
            """, self.user.id)

        embed = discord.Embed(
            title=f"📊 Aggregate Stats for {self.user.display_name}",
            color=discord.Color.green()
        )
        embed.add_field(name="❤️ Total Health", value=str(totals["total_health"]), inline=True)
        embed.add_field(name="🗡️ Total Attack", value=str(totals["total_attack"]), inline=True)
        embed.add_field(name="⚡ Total Speed", value=str(totals["total_speed"]), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="profile", description="Show your profile or another user's profile")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None):
        user = member or interaction.user
        user_id = int(user.id)

        async with self.bot.db.acquire() as conn:
            profile = await conn.fetchrow("""
                SELECT user_id, bloodcoins, created_at, updated_at, current_buddy_id
                FROM users
                WHERE user_id = $1
            """, user_id)

            if not profile:
                await interaction.response.send_message("⚠️ This user does not have a profile yet.", ephemeral=True)
                return

            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN c.rarity = 'common' THEN uc.quantity ELSE 0 END) AS commons,
                    SUM(CASE WHEN c.rarity = 'rare' THEN uc.quantity ELSE 0 END) AS rares,
                    SUM(CASE WHEN c.rarity = 'epic' THEN uc.quantity ELSE 0 END) AS epics,
                    SUM(CASE WHEN c.rarity = 'legendary' THEN uc.quantity ELSE 0 END) AS legendaries
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
            """, user_id)

            buddy = None
            if profile["current_buddy_id"]:
                buddy = await conn.fetchrow("""
                    SELECT name, image_url
                    FROM buddies
                    WHERE buddy_id = $1
                """, profile["current_buddy_id"])

        embed = discord.Embed(
            title=f"👤 Profile of {user.display_name}",
            color=discord.Color.gold() if stats["legendaries"] else discord.Color.blurple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="💰 Balance", value=f"{profile['bloodcoins']:,} BloodCoins", inline=True)
        embed.add_field(name="📅 Created", value=profile["created_at"].strftime("%d %b %Y"), inline=True)

        if profile["updated_at"]:
            embed.add_field(name="🔄 Last Update", value=profile["updated_at"].strftime("%d %b %Y"), inline=True)

        collection = (
            f"**Total:** {stats['total'] or 0}\n"
            f"{RARITY_EMOJIS['common']} {stats['commons'] or 0} | "
            f"{RARITY_EMOJIS['rare']} {stats['rares'] or 0} | "
            f"{RARITY_EMOJIS['epic']} {stats['epics'] or 0} | "
            f"{RARITY_EMOJIS['legendary']} {stats['legendaries'] or 0}"
        )
        embed.add_field(name="🃏 Collection", value=collection, inline=False)

        achievements = []
        if stats["legendaries"]:
            achievements.append("🏆 Legendary Owner")
        if profile["bloodcoins"] > 100000:
            achievements.append("💎 Wealthy")
        embed.add_field(name="🎖️ Achievements", value=", ".join(achievements) or "—", inline=False)

        if buddy:
            embed.add_field(name="🐾 Buddy", value=buddy["name"], inline=False)
            if buddy["image_url"]:
                embed.set_image(url=buddy["image_url"])

        view = ProfileView(user, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    async def cog_load(self):
        cmds = await self.bot.tree.fetch_commands(guild=discord.Object(id=GUILD_ID))
        names = [c.name for c in cmds]
        print(f"[Profile] Commands in tree for guild {GUILD_ID}: {names}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
