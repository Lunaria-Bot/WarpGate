# cogs/upgrade.py
import discord
from discord.ext import commands
from db import tx, pool

class UpgradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="upgrade")
    async def upgrade(self, ctx: commands.Context, card_id: str):
        async with tx() as conn:
            # Vérifie que l’utilisateur possède la carte
            uc = await conn.fetchrow("""
                SELECT uc.qty, uc.upgrade_level, c.name, c.rarity, c.potential,
                       c.image_url, c.description
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id=$1 AND uc.card_id=$2
            """, ctx.author.id, card_id)

            if not uc:
                await ctx.send("⚠️ Tu ne possèdes pas cette carte.")
                return

            if uc["upgrade_level"] >= 5:
                await ctx.send("⭐ Cette carte est déjà au niveau maximum.")
                return

            # Vérifie que l’utilisateur a assez de monnaie
            cur = await conn.fetchrow("SELECT blood_coins FROM currencies WHERE user_id=$1", ctx.author.id)
            cost = 10 * (uc["upgrade_level"] + 1)  # coût croissant
            if cur["blood_coins"] < cost:
                await ctx.send(f"💰 Il te faut {cost} Blood Coins pour améliorer cette carte.")
                return

            # Déduit le coût et upgrade
            await conn.execute(
                "UPDATE currencies SET blood_coins = blood_coins - $1 WHERE user_id=$2",
                cost, ctx.author.id
            )
            await conn.execute(
                "UPDATE user_cards SET upgrade_level = upgrade_level + 1 WHERE user_id=$1 AND card_id=$2",
                ctx.author.id, card_id
            )

        # Embed résultat
        new_level = uc["upgrade_level"] + 1
        stars = "★" * min(uc["potential"] + new_level, 5)

        embed = discord.Embed(
            title=f"✨ Upgrade réussi !",
            description=(
                f"Ta carte **{uc['name']}** évolue.\n\n"
                f"⭐ Potentiel: {stars}\n"
                f"Rareté: {uc['rarity']}\n\n"
                f"{uc['description'] or ''}"
            ),
            color=discord.Color.green()
        )
        if uc["image_url"]:
            embed.set_image(url=uc["image_url"])

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UpgradeCog(bot))
