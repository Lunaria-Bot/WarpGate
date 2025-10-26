import discord
from discord.ext import commands
from utils.db import db_transaction

class Team(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wsetteam")
    async def set_team(self, ctx, *codes: str):
        if not codes:
            return await ctx.send("❌ Tu dois fournir au moins un code de carte (ex: `GojoSatoru-base`).")

        discord_id = ctx.author.id

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                return await ctx.send("⚠️ Tu n’as pas encore de profil. Utilise `wregister`.")

            # Récupérer toutes les cartes possédées par le joueur
            owned = await conn.fetch("""
                SELECT uc.card_id, c.code, c.character_name, c.form
                FROM user_cards uc
                JOIN cards c ON c.id = uc.card_id
                WHERE uc.user_id = $1
            """, player_id)

            code_map = {row["code"].lower(): row["card_id"] for row in owned}
            card_ids = []

            for code in codes:
                normalized = code.lower().strip()
                if normalized not in code_map:
                    return await ctx.send(f"❌ Tu ne possèdes pas de carte avec le code `{code}`.")
                card_ids.append(code_map[normalized])

            # Supprimer l’équipe existante
            await conn.execute("DELETE FROM player_team WHERE player_id = $1", player_id)

            # Insérer la nouvelle équipe
            for slot, card_id in enumerate(card_ids, start=1):
                await conn.execute("""
                    INSERT INTO player_team (player_id, card_id, slot)
                    VALUES ($1, $2, $3)
                """, player_id, card_id, slot)

        await ctx.send(f"✅ Ton équipe a été mise à jour avec {len(card_ids)} carte(s).")

    @commands.command(name="wteam")
    async def show_team(self, ctx):
        discord_id = ctx.author.id

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                return await ctx.send("⚠️ Tu n’as pas encore de profil. Utilise `wregister`.")

            rows = await conn.fetch("""
                SELECT pt.slot, c.character_name, c.form, c.series
                FROM player_team pt
                JOIN cards c ON c.id = pt.card_id
                WHERE pt.player_id = $1
                ORDER BY pt.slot
            """, player_id)

        if not rows:
            return await ctx.send("ℹ️ Ton équipe est vide. Utilise `wsetteam` pour la définir.")

        embed = discord.Embed(title=f"📜 Équipe de {ctx.author.display_name}", color=discord.Color.blurple())
        for row in rows:
            embed.add_field(
                name=f"Slot {row['slot']}",
                value=f"**{row['character_name']}**\nForme: `{row['form']}`\nSérie: *{row['series'] or 'Inconnue'}*",
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Team(bot))
