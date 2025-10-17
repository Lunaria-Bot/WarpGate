import discord
from discord.ext import commands
import asyncio
import random
from .entities import entity_from_db, Entity

MIMIC_QUOTES = [
    "Treasure? Oh no, I’m the real reward.",
    "Curiosity tastes almost as good as fear.",
    "Funny how you never suspect the things you want most."
]

MIMIC_IMAGE = "https://media.discordapp.net/attachments/.../mimic.png"

class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="draw")
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def draw(self, ctx):
        msg = await ctx.send("🎴 Drawing...")
        await asyncio.sleep(2)

        # --- 10% chance Mimic ---
        if random.randint(1, 100) <= 10:
            # Get player's Buddy
            async with self.bot.db.acquire() as conn:
                buddy = await conn.fetchrow("""
                    SELECT c.*, uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                    FROM users u
                    JOIN cards c ON u.buddy_card_id = c.card_id
                    LEFT JOIN user_cards uc ON uc.card_id = c.card_id AND uc.user_id = u.user_id
                    WHERE u.user_id = $1
                """, ctx.author.id)

            if buddy:
                player = entity_from_db(
                    buddy,
                    user_card_row={"health": buddy["u_health"], "attack": buddy["u_attack"], "speed": buddy["u_speed"]}
                )
                player.description = f"Buddy of {ctx.author.display_name}"
            else:
                player = Entity(ctx.author.display_name, rarity="common", description="Adventurer without buddy")

            # Create Mimic
            mimic = Entity("Mimic", rarity="epic",
                           image_url=MIMIC_IMAGE,
                           description=random.choice(MIMIC_QUOTES),
                           override_stats={"health": 60, "attack": 15, "speed": 6})

            log = [f"👾 {mimic.name} appears!"]

            # Determine who starts
            turn_order = [player, mimic] if player.stats.speed >= mimic.stats.speed else [mimic, player]

            # Auto battle
            while player.is_alive() and mimic.is_alive():
                attacker, defender = turn_order
                dmg = attacker.attack_target(defender)
                log.append(f"**{attacker.name}** attacks → deals {dmg} damage to **{defender.name}** "
                           f"(Remaining HP: {defender.stats.health})")
                turn_order.reverse()

            winner = player if player.is_alive() else mimic
            log.append(f"🏆 **{winner.name}** wins the battle!")

            reward_embed = None
            if winner == player:
                async with self.bot.db.acquire() as conn:
                    # +50 Bloodcoins
                    await conn.execute("""
                        UPDATE users
                        SET bloodcoins = bloodcoins + 50
                        WHERE user_id = $1
                    """, ctx.author.id)

                    # Rarity roll
                    roll = random.random() * 100
                    if roll <= 90:
                        rarity = "rare"
                    elif roll <= 99.5:
                        rarity = "epic"
                    else:
                        rarity = "legendary"

                    # Draw a card of that rarity
                    card = await conn.fetchrow("""
                        SELECT *
                        FROM cards
                        WHERE rarity = $1
                        ORDER BY random()
                        LIMIT 1
                    """, rarity)

                reward_entity = entity_from_db(card)
                reward_embed = reward_entity.to_embed(title_prefix="🎁 Reward obtained:")
                reward_embed.description = f"You won **50 Bloodcoins** and a **{rarity.capitalize()}** card!"

            # Final combat embed
            combat_embed = discord.Embed(
                title="⚔️ Battle against the Mimic",
                description="\n".join(log),
                color=discord.Color.red()
            )
            if mimic.image_url:
                combat_embed.set_thumbnail(url=mimic.image_url)

            await msg.edit(content=None, embed=combat_embed)
            if reward_embed:
                await ctx.send(embed=reward_embed)
            return

        # --- Otherwise, normal draw ---
        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT *
                FROM cards
                WHERE rarity = 'common'
                ORDER BY random()
                LIMIT 1
            """)

        entity = entity_from_db(card)
        await msg.edit(content=None, embed=entity.to_embed())

    @draw.error
    async def draw_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = int(error.retry_after // 60)
            seconds = int(error.retry_after % 60)
            await ctx.send(
                f"⏳ You must wait **{minutes}m {seconds}s** before using `!draw` again.",
                delete_after=10
            )


async def setup(bot):
    await bot.add_cog(Draw(bot))
