import discord
from discord.ext import commands
from models.card import Card
from models.user_card import UserCard
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

FORM_COLORS = {
    "base": discord.Color.blue(),
    "awakened": discord.Color.gold(),
    "event": discord.Color.magenta()
}

class Buddy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="buddy")
    async def set_or_show_buddy(self, ctx, *, args: str = None):
        """
        - mbuddy -> shows the current buddy
        - mbuddy <card name> <form> -> sets this card as buddy
        """
        user_id = ctx.author.id

        async with self.bot.db.begin() as session:
            if not args:
                # Show current buddy
                result = await session.execute(
                    select(Card, UserCard)
                    .join(UserCard, Card.id == UserCard.card_id)
                    .join_from(UserCard, "users", isouter=True)
                    .where(UserCard.user_id == user_id)
                    .where(Card.id == select(Card.id).where(Card.id == select("buddy_card_id").where("user_id" == user_id)))
                )
                row = result.first()
                if not row:
                    await ctx.send("⚠️ You don’t have a Buddy yet. Use `mbuddy <card name> <form>` to set one.")
                    return

                card, uc = row
                level = uc.xp // 100 + 1
                embed = discord.Embed(
                    title=f"🤝 Buddy of {ctx.author.display_name}: {card.character_name}",
                    description=card.description or "No description available.",
                    color=FORM_COLORS.get(card.form, discord.Color.dark_gray())
                )
                embed.add_field(name="Form", value=card.form.capitalize(), inline=True)
                embed.add_field(name="Level", value=f"{level} ({uc.xp} XP)", inline=True)
                embed.add_field(name="Stats", value=f"❤️ {uc.health} | ⚔️ {uc.attack} | 💨 {uc.speed}", inline=False)
                if card.image_url:
                    embed.set_thumbnail(url=card.image_url)
                await ctx.send(embed=embed)
                return

            # Set new buddy
            try:
                *name_parts, form = args.split()
                character_name = " ".join(name_parts)
            except ValueError:
                await ctx.send("⚠️ Invalid format. Use `mbuddy <card name> <form>`.")
                return

            result = await session.execute(
                select(Card, UserCard)
                .join(UserCard, Card.id == UserCard.card_id)
                .where(UserCard.user_id == user_id)
                .where(Card.character_name.ilike(character_name))
                .where(Card.form == form.lower())
                .limit(1)
            )
            row = result.first()
            if not row:
                await ctx.send(f"⚠️ You don’t own '{character_name}' in form '{form}'.")
                return

            card, uc = row

            # Update buddy
            await session.execute(
                f"UPDATE users SET buddy_card_id = {card.id} WHERE user_id = {user_id}"
            )

            level = uc.xp // 100 + 1
            embed = discord.Embed(
                title=f"✅ Buddy set: {card.character_name} ({form})",
                description=card.description or "No description available.",
                color=FORM_COLORS.get(form, discord.Color.dark_gray())
            )
            embed.add_field(name="Level", value=f"{level} ({uc.xp} XP)", inline=True)
            embed.add_field(name="Stats", value=f"❤️ {uc.health} | ⚔️ {uc.attack} | 💨 {uc.speed}", inline=False)
            if card.image_url:
                embed.set_thumbnail(url=card.image_url)
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Buddy(bot))
