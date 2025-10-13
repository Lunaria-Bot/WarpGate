# cogs/register.py
import discord
from discord.ext import commands
from db import tx

class RegisterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register")
    async def register(self, ctx: commands.Context, avatar_id: str = None, faction_id: str = None):
        if not avatar_id or not faction_id:
            await ctx.send("Utilisation: !register <avatar_id> <faction_id>\nAvatars: AV1, AV2, AV3\nFactions: ASHEN, VERDANT, AZURE")
            return

        avatar_id = avatar_id.upper()
        faction_id = faction_id.upper()

        async with tx() as conn:
            av = await conn.fetchrow("SELECT avatar_id FROM avatars WHERE avatar_id=$1", avatar_id)
            fa = await conn.fetchrow("SELECT faction_id FROM factions WHERE faction_id=$1", faction_id)
            if not av or not fa:
                await ctx.send("Avatar ou faction invalide. Réessaie avec des valeurs valides.")
                return

            u = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", ctx.author.id)
            if not u:
                await conn.execute(
                    "INSERT INTO users (user_id, username, avatar_id, faction_id) VALUES ($1, $2, $3, $4)",
                    ctx.author.id, ctx.author.name, avatar_id, faction_id
                )
                await conn.execute("INSERT INTO currencies (user_id) VALUES ($1)", ctx.author.id)
            else:
                if u["avatar_id"] or u["faction_id"]:
                    await ctx.send("Tu es déjà enregistré.")
                    return
                await conn.execute(
                    "UPDATE users SET avatar_id=$1, faction_id=$2 WHERE user_id=$3",
                    avatar_id, faction_id, ctx.author.id
                )

        await ctx.send(f"Inscription réussie: avatar {avatar_id}, faction {faction_id}.")

async def setup(bot):
    await bot.add_cog(RegisterCog(bot))
