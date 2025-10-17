import discord
from discord.ext import commands
from .entities import entity_from_db

class Buddy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="buddy")
    async def set_or_show_buddy(self, ctx, *, args: str = None):
        """
        - !buddy -> shows the current buddy
        - !buddy <card name> <rarity> -> sets this card as buddy
        """
        async with self.bot.db.acquire() as conn:
            if not args:
                # Show current buddy
                buddy = await conn.fetchrow("""
                    SELECT c.*, uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                    FROM users u
                    JOIN cards c ON u.buddy_card_id = c.card_id
                    LEFT JOIN user_cards uc ON uc.card_id = c.card_id AND uc.user_id = u.user_id
                    WHERE u.user_id = $1
                """, ctx.author.id)

                if not buddy:
                    await ctx.send("⚠️ You don’t have a Buddy yet. Use `!buddy <card name> <rarity>` to set one.")
                    return

                entity = entity_from_db(
                    buddy,
                    user_card_row={"health": buddy["u_health"], "attack": buddy["u_attack"], "speed": buddy["u_speed"]}
                )
                embed = entity.to_embed(title_prefix=f"🤝 Buddy of {ctx.author.display_name}:")
                await ctx.send(embed=embed)
                return

            # Otherwise, set a new buddy
            try:
                *name_parts, rarity = args.split()
                card_name = " ".join(name_parts)
            except ValueError:
                await ctx.send("⚠️ Invalid format. Use `!buddy <card name> <rarity>`.")
                return

            card = await conn.fetchrow("""
                SELECT c.card_id, c.*, uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                FROM user_cards uc
                JOIN cards c ON uc.card_id = c.card_id
                WHERE uc.user_id = $1
                AND c.name ILIKE $2
                AND c.rarity ILIKE $3
            """, ctx.author.id, card_name, rarity)

            if not card:
                await ctx.send("⚠️ You don’t own this card.")
                return

            # Update buddy (replaces the previous one if any)
            await conn.execute("""
                UPDATE users
                SET buddy_card_id = $1
                WHERE user_id = $2
            """, card["card_id"], ctx.author.id)

        await ctx.send(f"✅ Your new Buddy is **{card['name']} ({card['rarity'].capitalize()})** !")


async def setup(bot):
    await bot.add_cog(Buddy(bot))
