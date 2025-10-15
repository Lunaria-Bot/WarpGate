import discord
from discord.ext import commands

class CooldownReset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="resetdraw")
    @commands.has_permissions(administrator=True)  # réservé aux admins
    async def reset_draw_cooldown(self, ctx, member: discord.Member = None):
        """Réinitialise le cooldown de la commande !draw pour un membre (ou toi-même si aucun membre précisé)."""
        target = member or ctx.author
        command = self.bot.get_command("draw")

        if command is None:
            await ctx.send("❌ La commande !draw n'existe pas.")
            return

        # Accéder au mapping des cooldowns
        bucket = command._buckets.get_bucket(ctx.message)
        if bucket is None:
            await ctx.send("❌ Impossible de trouver le cooldown.")
            return

        # Reset du cooldown pour ce membre
        bucket._cooldown.reset()
        bucket._tokens = bucket._cooldown.rate
        bucket._window = 0

        await ctx.send(f"✅ Cooldown de !draw réinitialisé pour {target.mention}")

async def setup(bot):
    await bot.add_cog(CooldownReset(bot))
