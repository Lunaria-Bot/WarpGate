import discord
from discord.ext import commands, menus

RARITY_EMOJIS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡"
}

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        """Show the user's card inventory with pagination."""
        user_id = int(ctx.author.id)

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.base_name, c.name, c.rarity, uc.quantity
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
                ORDER BY 
                    CASE c.rarity
                        WHEN 'legendary' THEN 1
                        WHEN 'epic' THEN 2
                        WHEN 'rare' THEN 3
                        ELSE 4
                    END,
                    c.base_name
            """, user_id)

            balance = await conn.fetchval("""
                SELECT bloodcoins FROM users WHERE user_id = $1
            """, user_id)

        if not rows:
            await ctx.send("📭 Your inventory is empty. Use `!draw` to get cards!")
            return

        # Split inventory into pages of 10 cards
        pages = []
        for i in range(0, len(rows), 10):
            chunk = rows[i:i+10]
            embed = discord.Embed(
                title=f"🎴 {ctx.author.display_name}'s Inventory",
                description=f"💰 Bloodcoins: **{balance}**",
                color=discord.Color.blurple()
            )
            for row in chunk:
                rarity_icon = RARITY_EMOJIS.get(row["rarity"], "❔")
                embed.add_field(
                    name=f"{rarity_icon} {row['name']}",
                    value=f"Rarity: {row['rarity'].capitalize()} | Qty: {row['quantity']}",
                    inline=False
                )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            pages.append(embed)

        # Simple paginator with reactions
        current = 0
        message = await ctx.send(embed=pages[current])
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                if str(reaction.emoji) == "➡️" and current < len(pages) - 1:
                    current += 1
                    await message.edit(embed=pages[current])
                elif str(reaction.emoji) == "⬅️" and current > 0:
                    current -= 1
                    await message.edit(embed=pages[current])
                await message.remove_reaction(reaction, user)
            except Exception:
                break


async def setup(bot):
    await bot.add_cog(Inventory(bot))
