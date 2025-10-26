import discord
from discord.ext import commands
from typing import Optional
from utils.db import db_transaction

FORM_EMOJIS = {
    "base": "🔵",
    "awakened": "🟣",
    "event": "🎉"
}

def get_level(xp: int) -> int:
    return xp // 100 + 1

class Team(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="wsetteam")
    async def set_team(self, ctx, *card_ids: int):
        """Assign up to 5 cards to your team. First one becomes captain."""
        if not card_ids or len(card_ids) > 5:
            await ctx.send("⚠️ You must provide between 1 and 5 card IDs.")
            return

        discord_id = str(ctx.author.id)

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                await ctx.send("⚠️ You don't have a profile yet. Use `wregister` to create one.")
                return

            # Validate ownership
            owned_ids = await conn.fetch(
                "SELECT card_id FROM user_cards WHERE user_id = $1 AND card_id = ANY($2::int[])",
                player_id, list(card_ids)
            )
            owned_set = {row["card_id"] for row in owned_ids}
            invalid = [cid for cid in card_ids if cid not in owned_set]
            if invalid:
                await ctx.send(f"❌ You don't own these card(s): {', '.join(map(str, invalid))}")
                return

            # Clear previous team
            await conn.execute("DELETE FROM player_team WHERE user_id = $1", player_id)

            # Insert new team
            for i, card_id in enumerate(card_ids):
                await conn.execute("""
                    INSERT INTO player_team (user_id, slot, card_id, is_captain)
                    VALUES ($1, $2, $3, $4)
                """, player_id, i + 1, card_id, i == 0)

        await ctx.send(f"✅ Team updated. {len(card_ids)} card(s) assigned. Captain: `{card_ids[0]}`")

    @commands.command(name="team")
    async def show_team(self, ctx, member: Optional[discord.Member] = None):
        """Display your current team lineup."""
        user = member or ctx.author
        discord_id = str(user.id)

        async with db_transaction(self.bot.db) as conn:
            player_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not player_id:
                await ctx.send("⚠️ You don't have a profile yet. Use `wregister` to create one.")
                return

            team_rows = await conn.fetch("""
                SELECT pt.slot, pt.is_captain, c.id AS card_id, c.character_name, c.form,
                       uc.xp, uc.health, uc.attack, uc.speed
                FROM player_team pt
                JOIN user_cards uc ON uc.card_id = pt.card_id AND uc.user_id = pt.user_id
                JOIN cards c ON c.id = pt.card_id
                WHERE pt.user_id = $1
                ORDER BY pt.slot
            """, player_id)

        if not team_rows:
            await ctx.send("📭 No team configured. Use `wsetteam` to assign cards.")
            return

        total_hp = sum(row["health"] for row in team_rows)
        total_recovery = sum(row["speed"] for row in team_rows)

        embed = discord.Embed(
            title=f"{user.display_name}'s team 🏆",
            description=f"❤️ Total HP: **{total_hp}**\n🔁 Recovery: **{total_recovery}**",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        for row in team_rows:
            emoji = FORM_EMOJIS.get(row["form"], "❔")
            level = get_level(row["xp"])
            role = " (Captain)" if row["is_captain"] else ""
            embed.add_field(
                name=f"{emoji} {row['character_name']}{role}",
                value=f"ID: `{row['card_id']}` • Level: `{level}`",
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Team(bot))
