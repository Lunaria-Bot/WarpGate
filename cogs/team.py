import discord
from discord.ext import commands
from utils.db import db_transaction

class Team(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wsetteam")
    async def set_team(self, ctx, *codes: str):
        if not codes:
            return await ctx.send("❌ You must provide at least one card code (e.g. `GojoSatoru-base`).")

        discord_id = str(ctx.author.id)

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                return await ctx.send("⚠️ You don't have a profile yet. Use `wregister`.")

            owned = await conn.fetch("""
                SELECT uc.card_id, c.code
                FROM user_cards uc
                JOIN cards c ON c.id = uc.card_id
                WHERE uc.user_id = $1
            """, player_id)

            code_map = {row["code"].lower(): row["card_id"] for row in owned}
            card_ids = []

            for code in codes:
                normalized = code.lower().strip()
                if normalized not in code_map:
                    return await ctx.send(f"❌ You don't own a card with code `{code}`.")
                card_ids.append(code_map[normalized])

            await conn.execute("DELETE FROM player_team WHERE player_id = $1", player_id)

            for slot, card_id in enumerate(card_ids, start=1):
                await conn.execute("""
                    INSERT INTO player_team (player_id, card_id, slot)
                    VALUES ($1, $2, $3)
                """, player_id, card_id, slot)

        await ctx.send(f"✅ Your team has been updated with {len(card_ids)} card(s).")

    @commands.command(name="wteam")
    async def show_team(self, ctx):
        discord_id = str(ctx.author.id)

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                return await ctx.send("⚠️ You don't have a profile yet. Use `wregister`.")

            rows = await conn.fetch("""
                SELECT pt.slot, c.character_name, c.form, c.series
                FROM player_team pt
                JOIN cards c ON c.id = pt.card_id
                WHERE pt.player_id = $1
                ORDER BY pt.slot
            """, player_id)

        if not rows:
            return await ctx.send("ℹ️ Your team is empty. Use `wsetteam` to define it.")

        embed = discord.Embed(title=f"📜 {ctx.author.display_name}'s Team", color=discord.Color.blurple())
        for row in rows:
            embed.add_field(
                name=f"Slot {row['slot']}",
                value=f"**{row['character_name']}**\nForm: `{row['form']}`\nSeries: *{row['series'] or 'Unknown'}*",
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Team(bot))
