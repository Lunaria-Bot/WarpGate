import discord
from discord.ext import commands

UPGRADE_RULES = {
    "common": {"next": "rare", "cost": 2000, "copies": 5},
    "rare": {"next": "epic", "cost": 5000, "copies": 20},
    "epic": {"next": "legendary", "cost": 10000, "copies": 50}
}

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

class Upgrade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="upgrade")
    async def upgrade(self, ctx, card_id: int):
        """Upgrade a card into its next rarity version."""
        user_id = ctx.author.id

        async with self.bot.db.acquire() as conn:
            # 1. Fetch user balance
            balance = await conn.fetchval(
                "SELECT bloodcoins FROM users WHERE user_id = $1", user_id
            )
            if balance is None:
                await ctx.send("⚠️ You don't have a profile yet.")
                return

            # 2. Fetch the card the user owns
            card = await conn.fetchrow("""
                SELECT uc.quantity, c.card_id, c.name, c.rarity, c.base_name
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1 AND uc.card_id = $2
            """, user_id, card_id)

            if not card:
                await ctx.send("⚠️ You don't own this card.")
                return

            rarity = card["rarity"].lower()
            if rarity not in UPGRADE_RULES:
                await ctx.send("⚠️ This card cannot be upgraded further.")
                return

            rule = UPGRADE_RULES[rarity]
            next_rarity = rule["next"]

            # 3. Check requirements
            if balance < rule["cost"]:
                await ctx.send(f"❌ You need {rule['cost']} BloodCoins to upgrade.")
                return
            if card["quantity"] < rule["copies"]:
                await ctx.send(f"❌ You need {rule['copies']} copies of this card to upgrade.")
                return

            # 4. Find the upgraded version of this card
            next_card = await conn.fetchrow("""
                SELECT card_id, name, rarity, image_url, description, potential
                FROM cards
                WHERE base_name = $1 AND rarity = $2
            """, card["base_name"], next_rarity)

            if not next_card:
                await ctx.send(f"⚠️ No upgraded version found for {card['name']} → {next_rarity}.")
                return

            # 5. Transaction: deduct coins, remove copies, add upgraded card
            async with conn.transaction():
                await conn.execute(
                    "UPDATE users SET bloodcoins = bloodcoins - $1 WHERE user_id = $2",
                    rule["cost"], user_id
                )
                await conn.execute(
                    "UPDATE user_cards SET quantity = quantity - $1 WHERE user_id = $2 AND card_id = $3",
                    rule["copies"], user_id, card["card_id"]
                )
                await conn.execute("""
                    INSERT INTO user_cards (user_id, card_id, quantity)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (user_id, card_id)
                    DO UPDATE SET quantity = user_cards.quantity + 1
                """, user_id, next_card["card_id"])

        # 6. Confirmation embed
        potential = int(next_card["potential"]) if next_card["potential"] is not None else 0

        embed = discord.Embed(
            title="🔼 Upgrade Successful!",
            description=f"{card['name']} has been upgraded to **{next_card['name']}**!",
            color=RARITY_COLORS.get(next_rarity, discord.Color.dark_gray())
        )
        embed.add_field(name="Cost", value=f"{rule['cost']} BloodCoins", inline=True)
        embed.add_field(name="Copies Used", value=str(rule["copies"]), inline=True)
        embed.add_field(name="New Potential", value="⭐" * potential, inline=True)

        if next_card["image_url"]:
            embed.set_thumbnail(url=next_card["image_url"])

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Upgrade(bot))
