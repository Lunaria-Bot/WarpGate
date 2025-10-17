import discord
from discord.ext import commands
from .entities import entity_from_db  # uses stat hierarchy: user_cards > cards > rarity base

# Upgrade rules: cost in Bloodcoins + copies required
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

# --- Helper: update quest progress ---
async def update_quest_progress(conn, user_id: int, quest_desc: str, amount: int = 1):
    """Increment quest progress for a given quest description."""
    await conn.execute("""
        UPDATE user_quests uq
        SET progress = progress + $3,
            completed = (progress + $3) >= qt.target
        FROM quest_templates qt
        WHERE uq.quest_id = qt.quest_id
          AND uq.user_id = $1
          AND qt.description = $2
          AND uq.claimed = FALSE
    """, user_id, quest_desc, amount)


class Upgrade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="upgrade")
    async def upgrade(self, ctx, *, args: str):
        """
        Upgrade a card by name and rarity.
        Example: !upgrade Makima Common
                 !upgrade Maki Zenin Common
        """
        user_id = int(ctx.author.id)

        # Split into card name + rarity
        parts = args.rsplit(" ", 1)
        if len(parts) != 2:
            await ctx.send("⚠️ Usage: !upgrade <card name> <rarity>")
            return

        base_name, rarity = parts
        rarity = rarity.lower()

        if rarity not in UPGRADE_RULES:
            await ctx.send("⚠️ This rarity cannot be upgraded (or is invalid).")
            return

        rule = UPGRADE_RULES[rarity]
        next_rarity = rule["next"]

        async with self.bot.db.acquire() as conn:
            # 1) Check user balance
            balance = await conn.fetchval(
                "SELECT bloodcoins FROM users WHERE user_id = $1", user_id
            )
            if balance is None:
                await ctx.send("⚠️ You don't have a profile yet.")
                return

            # 2) Fetch current card + stats (cards & user_cards overrides)
            card = await conn.fetchrow("""
                SELECT uc.quantity,
                       c.card_id, c.name, c.rarity, c.base_name, c.image_url, c.description, c.potential,
                       c.health, c.attack, c.speed,
                       uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
                  AND LOWER(c.base_name) = LOWER($2)
                  AND c.rarity = $3
            """, user_id, base_name.strip(), rarity)

            if not card:
                await ctx.send(f"⚠️ You don't own {base_name} ({rarity.capitalize()}).")
                return

            # Build entity for old stats (effective)
            old_entity = entity_from_db(card, {
                "health": card["u_health"], "attack": card["u_attack"], "speed": card["u_speed"]
            })
            old_h, old_a, old_s = old_entity.stats.health, old_entity.stats.attack, old_entity.stats.speed

            # 3) Check requirements
            if balance < rule["cost"]:
                await ctx.send(f"❌ You need {rule['cost']} BloodCoins to upgrade.")
                return
            if card["quantity"] < rule["copies"]:
                await ctx.send(f"❌ You need {rule['copies']} copies of this card to upgrade.")
                return

            # 4) Fetch upgraded version with stats
            next_card = await conn.fetchrow("""
                SELECT card_id, name, rarity, image_url, description, potential,
                       health, attack, speed
                FROM cards
                WHERE base_name = $1 AND rarity = $2
                LIMIT 1
            """, card["base_name"], next_rarity)

            if not next_card:
                await ctx.send(f"⚠️ No upgraded version found for {card['name']} → {next_rarity}.")
                return

            # Build entity for new stats (effective; user_cards overrides won't exist yet)
            new_entity = entity_from_db(next_card)
            new_h, new_a, new_s = new_entity.stats.health, new_entity.stats.attack, new_entity.stats.speed

            # 5) Transaction: remove coins + copies, add upgraded card
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

                # ✅ Update quest progress
                await update_quest_progress(conn, user_id, "Upgrade 1 card", 1)
                await update_quest_progress(conn, user_id, "Upgrade 2 cards", 1)
                await update_quest_progress(conn, user_id, "Upgrade 10 cards", 1)

        # 6) Confirmation embed with stats comparison
        potential = int(next_card["potential"]) if next_card["potential"] is not None else 0

        embed = discord.Embed(
            title="🔼 Upgrade Successful!",
            description=f"{card['name']} has been upgraded to **{next_card['name']}**!",
            color=RARITY_COLORS.get(next_rarity, discord.Color.dark_gray())
        )
        embed.add_field(name="Cost", value=f"{rule['cost']} BloodCoins", inline=True)
        embed.add_field(name="Copies Used", value=str(rule["copies"]), inline=True)
        embed.add_field(name="New Potential", value=("⭐" * potential) if potential > 0 else "—", inline=True)

        # Stats comparison
        stats_before = f"❤️ {old_h} | 🗡️ {old_a} | ⚡ {old_s}"
        stats_after  = f"❤️ {new_h} | 🗡️ {new_a} | ⚡ {new_s}"
        delta_h = new_h - old_h
        delta_a = new_a - old_a
        delta_s = new_s - old_s
        stats_delta = f"+❤️ {delta_h} | +🗡️ {delta_a} | +⚡ {delta_s}"

        embed.add_field(name="Stats before", value=stats_before, inline=False)
        embed.add_field(name="Stats after", value=stats_after, inline=False)
        embed.add_field(name="Change", value=stats_delta, inline=False)

        if next_card["image_url"]:
            embed.set_thumbnail(url=next_card["image_url"])

        await ctx.send(embed=embed)

    @commands.command(name="upgradeinfo")
    async def upgradeinfo(self, ctx):
        """Show upgrade requirements for each rarity."""
        embed = discord.Embed(
            title="📖 Upgrade Rules",
            description="Here are the requirements to upgrade your cards:",
            color=discord.Color.blurple()
        )

        for rarity, rule in UPGRADE_RULES.items():
            next_rarity = rule["next"].capitalize()
            cost = rule["cost"]
            copies = rule["copies"]

            embed.add_field(
                name=f"{rarity.capitalize()} ➝ {next_rarity}",
                value=f"💰 Cost: {cost} BloodCoins\n🃏 Copies: {copies}",
                inline=False
            )

        embed.set_footer(text="Legendary cards cannot be upgraded further.")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Upgrade(bot))
