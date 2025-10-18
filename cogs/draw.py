import discord
from discord.ext import commands
import asyncio
import random
from .entities import entity_from_db, Entity
from utils.leveling import add_xp  # XP helper

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
    @commands.cooldown(1, 600, commands.BucketType.user)  # 1 use every 10 min
    async def draw(self, ctx):
        user_id = int(ctx.author.id)

        # --- Check ban / bypass flags ---
        async with self.bot.db.acquire() as conn:
            flags = await conn.fetchrow("""
                SELECT banned, ban_reason, bypass_draw
                FROM users
                WHERE user_id = $1
            """, user_id)

        if flags and flags["banned"]:
            reason = flags["ban_reason"] or "No reason provided"
            await ctx.send(f"⛔ Your account is banned. Reason: {reason}")
            return

        if flags and flags["bypass_draw"]:
            self.draw.reset_cooldown(ctx)

        # 1) Animation
        anim_embed = discord.Embed(description="🎴 Drawing in progress...", color=discord.Color.blurple())
        anim_embed.set_image(url=DRAW_ANIM)
        msg = await ctx.send(embed=anim_embed)
        await asyncio.sleep(2)

        # 2) Mimic encounter (10%)
        if random.randint(1, 100) <= 10:
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
                player.name = buddy_row["name"]
            else:
                player = Entity(ctx.author.display_name, rarity="common", description="Adventurer without buddy")

            mimic = Entity("Mimic", rarity="epic",
                           image_url=MIMIC_IMAGE,
                           description=random.choice(MIMIC_QUOTES),
                           override_stats={"health": 60, "attack": 15, "speed": 6})

            log = [f"👾 {mimic.name} appears!"]
            turn_order = [player, mimic] if player.stats.speed >= mimic.stats.speed else [mimic, player]

            while player.is_alive() and mimic.is_alive():
                attacker, defender = turn_order
                dmg = attacker.attack_target(defender)
                log.append(f"**{attacker.name}** attacks → {dmg} dmg to **{defender.name}** "
                           f"(HP left: {defender.stats.health})")
                turn_order.reverse()

            winner = player if player.is_alive() else mimic
            log.append(f"🏆 **{winner.name}** wins the battle!")

            reward_embed = None
            if winner == player:
                async with self.bot.db.acquire() as conn:
                    await conn.execute("""
                        UPDATE users
                        SET bloodcoins = bloodcoins + 50
                        WHERE user_id = $1
                    """, user_id)

                    roll = random.random() * 100
                    if roll <= 90:
                        loot_rarity = "rare"
                    elif roll <= 99.5:
                        loot_rarity = "epic"
                    else:
                        loot_rarity = "legendary"

                    loot_card = await conn.fetchrow("""
                        SELECT *
                        FROM cards
                        WHERE rarity = $1
                        ORDER BY random()
                        LIMIT 1
                    """, loot_rarity)

                    if loot_card:
                        await conn.execute("""
                            INSERT INTO user_cards (user_id, card_id, quantity)
                            VALUES ($1, $2, 1)
                            ON CONFLICT (user_id, card_id)
                            DO UPDATE SET quantity = user_cards.quantity + 1
                        """, user_id, loot_card["card_id"])

                if loot_card:
                    reward_entity = entity_from_db(loot_card)
                    reward_embed = reward_entity.to_embed(title_prefix="🎁 Reward obtained:")
                    reward_embed.description = f"You earned **50 Bloodcoins** and a **{loot_rarity.capitalize()}** card!"

                leveled_up, new_level = await add_xp(self.bot, user_id, 5)
                if leveled_up:
                    await ctx.send(f"🎉 {ctx.author.mention} leveled up to **Level {new_level}**!")

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
            # 3) Normal draw
        async with self.bot.db.acquire() as conn:
            card = await conn.fetchrow("""
                SELECT *
                FROM cards
                WHERE rarity = 'common'
                ORDER BY random()
                LIMIT 1
            """)

            if not card:
                await msg.edit(content="⚠️ No common cards available.", attachments=[], embed=None)
                return

            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, user_id, card["card_id"])

            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + 10
                WHERE user_id = $1
            """, user_id)

            await update_quest_progress(conn, user_id, "Draw 5 times", 1)
            await update_quest_progress(conn, user_id, "Draw 10 times", 1)
            await update_quest_progress(conn, user_id, "Draw 100 times", 1)

        rarity = card["rarity"]
        potential = int(card["potential"]) if card["potential"] else 0

        result_entity = entity_from_db(card)
        result_embed = result_entity.to_embed(title_prefix="✨ You drew:")
        result_embed.title = f"✨ You drew: {card['name']} ✨"
        result_embed.color = RARITY_COLORS.get(rarity, discord.Color.dark_gray())
        result_embed.add_field(
            name="Potential",
            value=("⭐" * potential) if potential > 0 else "—",
            inline=True
        )

        await msg.edit(content=None, attachments=[], embed=result_embed)

        # --- Gain XP (+5) ---
        leveled_up, new_level = await add_xp(self.bot, user_id, 5)
        if leveled_up:
            await ctx.send(f"🎉 {ctx.author.mention} leveled up to **Level {new_level}**!")

    @draw.error
    async def draw_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = int(error.retry_after // 60)
            seconds = int(error.retry_after % 60)
            await ctx.send(
                f"⏳ You need to wait **{minutes}m {seconds}s** before using `!draw` again!",
                delete_after=10
            )
        else:
            await ctx.send("⚠️ An unexpected error occurred while processing your draw.", delete_after=10)


async def setup(bot):
    await bot.add_cog(Draw(bot))
