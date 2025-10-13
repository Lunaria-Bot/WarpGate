# cogs/profile.py
import discord
from discord.ext import commands
from db import pool

class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile")
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        async with pool().acquire() as conn:
            u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", target.id)
            if not u:
                await ctx.send("Utilisateur non enregistré. Utilise !register.")
                return
            c = await conn.fetchrow("SELECT blood_coins, noble_coins FROM currencies WHERE user_id=$1", target.id)
            await ctx.send(
                f"Profil de {target.display_name}\n"
                f"Avatar: {u['avatar_id'] or 'N/A'} | Faction: {u['faction_id'] or 'N/A'}\n"
                f"Niveau: {u['level']} | Blood coins: {c['blood_coins']} | Noble coins: {c['noble_coins']}\n"
                f"Badges: {u['badges']} | Equipement: {u['equipment']}"
            )

async def setup(bot):
    await bot.add_cog(ProfileCog(bot))
