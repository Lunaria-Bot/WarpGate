import discord
from discord.ext import commands
import asyncio
import random
from .entities import entity_from_db, Entity  # uses stat hierarchy: user_cards > cards > rarity base

RARITY_COLORS = {
    "common": discord.Color.light_gray(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold()
}

# --- Mimic data ---
MIMIC_QUOTES = [
    "Treasure? Oh no, I’m the real reward.",
    "Curiosity tastes almost as good as fear.",
    "Funny how you never suspect the things you want most."
]

MIMIC_IMAGE = "https://media.discordapp.net/attachments/1428401795364814948/1428401824024756316/image.png?format=webp&quality=lossless&width=880&height=493"

DRAW_ANIM = ("https://media.discordapp.net/attachments/1390792811380478032/1428014081927024734/"
             "AZnoEBWwS3YhAlSY-j6uUA-AZnoEBWw4TsWJ2XCcPMwOQ.gif")

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


class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="draw")
    @commands.cooldown(1, 600, commands.BucketType.user)  # 1 use every 600s (10 min) per user
    async def draw(self, ctx):
        """
        Draw a card with a 10% chance of encountering a Mimic instead.
        Normal draw: +10 Bloodcoins, adds a random common card to inventory, updates quests.
        Mimic: autobattle using player's Buddy stats; if win → +50 Bloodcoins + loot card with 90% Rare / 9.5% Epic / 0.5% Legendary.
        """
        user_id = int(ctx.author.id)

        # 1) Animation GIF
        anim_embed = discord.Embed(description="🎴 Drawing in progress...", color=discord.Color.blurple())
        anim_embed.set_image(url=DRAW_ANIM)
        msg = await ctx.send(embed=anim_embed)
        await asyncio.sleep(2)

        # 2) Check Mimic encounter (10%)
        if random.randint(1, 100) <= 10:
            # Build Player from Buddy (with stat hierarchy)
            async with self.bot.db.acquire() as conn:
                buddy_row = await conn.fetchrow("""
                    SELECT c.*, uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                    FROM users u
                    JOIN cards c ON u.buddy_card_id = c.card_id
                    LEFT JOIN user_cards uc ON uc.card_id = c.card_id AND uc.user_id = u.user_id
                    WHERE u.user_id = $1
                """, user_id)

            if buddy_row:
                player = entity_from_db(
                    buddy_row,
                    user_card_row={"health": buddy_row["u_health"], "attack": buddy_row["u_attack"], "speed": buddy_row["u_speed"]}
                )
                player.description = f"Buddy of {ctx.author.display_name}"
                player_name = buddy_row["name"]  # display buddy card name as player name
                player.name = player_name
            else:
                player = Entity(ctx.author.display_name, rarity="common", description="Adventurer without buddy")

            # Create Mimic entity (fixed stats for now)
            mimic = Entity("Mimic", rarity="epic",
                           image_url=MIMIC_IMAGE,
                           description=random.choice(MIMIC_QUOTES),
                           override_stats={"health": 60, "attack": 15, "speed": 6})

            # Battle log
            log = [f"👾 {mimic.name} appears!"]

            # Determine first turn
            turn_order = [player, mimic] if player.stats.speed >= mimic.stats.speed else [mimic, player]

            # Autobattle
            while player.is_alive() and mimic.is_alive():
                attacker, defender = turn_order
                dmg = attacker.attack_target(defender)
                log.append(f"**{attacker.name}** attacks → deals {dmg} damage to **{defender.name}** "
                           f"(HP left: {defender.stats.health})")
                turn_order.reverse()

            winner = player if player.is_alive() else mimic
            log.append(f"🏆 **{winner.name}** wins the battle!")

            reward_embed = None
            # Rewards if player wins
            if winner == player:
                async with self.bot.db.acquire() as conn:
                    # +50 Bloodcoins
                    await conn.execute("""
                        UPDATE users
                        SET bloodcoins = bloodcoins + 50
                        WHERE user_id = $1
                    """, user_id)

                    # Rarity roll: 90% Rare, 9.5% Epic, 0.5% Legendary
                    roll = random.random() * 100
                    if roll <= 90:
                        loot_rarity = "rare"
                    elif roll <= 99.5:
                        loot_rarity = "epic"
                    else:
                        loot_rarity = "legendary"

                    # Draw a loot card of that rarity
                    loot_card = await conn.fetchrow("""
                        SELECT card_id, base_name, name, rarity, potential, image_url, description,
                               health, attack, speed
                        FROM cards
                        WHERE rarity = $1
                        ORDER BY random()
                        LIMIT 1
                    """, loot_rarity)

                    if loot_card:
                        # Add to inventory (quantity)
                        await conn.execute("""
                            INSERT INTO user_cards (user_id, card_id, quantity)
                            VALUES ($1, $2, 1)
                            ON CONFLICT (user_id, card_id)
                            DO UPDATE SET quantity = user_cards.quantity + 1
                        """, user_id, loot_card["card_id"])

                # Build reward embed via entity_from_db (uses card stats if set)
                if loot_card:
                    reward_entity = entity_from_db(loot_card)
                    reward_embed = reward_entity.to_embed(title_prefix="🎁 Reward obtained:")
                    reward_embed.description = f"You earned **50 Bloodcoins** and a **{loot_rarity.capitalize()}** card!"

            # Final combat embed (log)
            combat_embed = discord.Embed(
                title="⚔️ Battle against the Mimic",
                description="\n".join(log),
                color=discord.Color.red()
            )
            if mimic.image_url:
                combat_embed.set_thumbnail(url=mimic.image_url)

            await msg.edit(embed=combat_embed, content=None, attachments=[])
            if reward_embed:
                await ctx.send(embed=reward_embed)
            return

        # 3) Normal draw logic
        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT card_id, base_name, name, rarity, potential, image_url, description,
                       health, attack, speed
                FROM cards
                WHERE rarity = 'common'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await msg.edit(content="⚠️ No common cards available in the database.", attachments=[], embed=None)
                return

            # Add card to inventory
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, user_id, card["card_id"])

            # +10 Bloodcoins for normal draw
            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10
                WHERE user_id = $1
            """, user_id)

            # Quest progress updates
            await update_quest_progress(conn, user_id, "Draw 5 times", 1)
            await update_quest_progress(conn, user_id, "Draw 10 times", 1)
            await update_quest_progress(conn, user_id, "Draw 100 times", 1)

        rarity = card["rarity"]
        potential = int(card["potential"]) if card["potential"] is not None else 0

        # Build result embed (use entity_from_db to keep stat hierarchy; but show potential and rarity color)
        result_entity = entity_from_db(card)
        result_embed = result_entity.to_embed(title_prefix="✨ You drew:")
        result_embed.title = f"✨ You drew: {card['name']} ✨"
        result_embed.color = RARITY_COLORS.get(rarity, discord.Color.dark_gray())
        result_embed.add_field(name="Potential", value=("⭐" * potential) if potential > 0 else "—", inline=True)

        await msg.edit(content=None, attachments=[], embed=result_embed)

    @draw.error
    async def draw_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = int(error.retry_after // 60)
            seconds = int(error.retry_after % 60)
            await ctx.send(
                f"⏳ You need to wait **{minutes}m {seconds}s** before using `!draw` again!",
                delete_after=10
            )


async def setup(bot):
    await bot.add_cog(Draw(bot))
