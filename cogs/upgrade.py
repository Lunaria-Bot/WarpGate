import discord
from discord.ext import commands

# Règles d’upgrade : coût en Bloodcoins + copies nécessaires
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

@commands.command(name="upgrade")
async def upgrade(self, ctx, *, args: str):
    """
    Upgrade a card by name and rarity.
    Exemple: !upgrade Makima Common
             !upgrade Maki Zenin Common
    """
    user_id = int(ctx.author.id)

    # Liste des raretés valides
    valid_rarities = ["common", "rare", "epic", "legendary"]

    # On coupe la chaîne en 2 : nom + rareté
    parts = args.rsplit(" ", 1)
    if len(parts) != 2:
        await ctx.send("⚠️ Usage: !upgrade <card name> <rarity>")
        return

    base_name, rarity = parts
    rarity = rarity.lower()

    if rarity not in UPGRADE_RULES:
        await ctx.send("⚠️ This rarity cannot be upgraded (or is invalid).")
        return

    async with self.bot.db.acquire() as conn:
        # 1. Vérifie le solde du joueur
        balance = await conn.fetchval(
            "SELECT bloodcoins FROM users WHERE user_id = $1", user_id
        )
        if balance is None:
            await ctx.send("⚠️ You don't have a profile yet.")
            return

        # 2. Récupère la carte actuelle (par nom + rareté)
        card = await conn.fetchrow("""
            SELECT uc.quantity, c.card_id, c.name, c.rarity, c.base_name
            FROM user_cards uc
            JOIN cards c ON c.card_id = uc.card_id
            WHERE uc.user_id = $1
              AND LOWER(c.base_name) = LOWER($2)
              AND c.rarity = $3
        """, user_id, base_name.strip(), rarity)

        if not card:
            await ctx.send(f"⚠️ You don't own {base_name} ({rarity.capitalize()}).")
            return

        rule = UPGRADE_RULES[rarity]
        next_rarity = rule["next"]

        # 3. Vérifie les conditions
        if balance < rule["cost"]:
            await ctx.send(f"❌ You need {rule['cost']} BloodCoins to upgrade.")
            return
        if card["quantity"] < rule["copies"]:
            await ctx.send(f"❌ You need {rule['copies']} copies of this card to upgrade.")
            return

        # 4. Trouve la carte de rareté supérieure
        next_card = await conn.fetchrow("""
            SELECT card_id, name, rarity, image_url, description, potential
            FROM cards
            WHERE base_name = $1 AND rarity = $2
        """, card["base_name"], next_rarity)

        if not next_card:
            await ctx.send(f"⚠️ No upgraded version found for {card['name']} → {next_rarity}.")
            return

        # 5. Transaction : retirer coins + copies, ajouter la carte supérieure
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

    # 6. Embed de confirmation
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
