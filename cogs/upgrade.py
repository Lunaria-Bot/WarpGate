import discord
from discord.ext import commands
from discord.ui import View, Button, Select
import random
from .entities import entity_from_db

# Upgrade rules
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

# NPC images
NPC_IMAGE = "https://media.discordapp.net/attachments/1428075046454431784/1429064750435926087/image.png"
MIRROR_IMAGE = "https://media.discordapp.net/attachments/1390792811380478032/1428895604624457828/A_stylized_anime_girl_rendered_entirely_from_swirling_dynamic_shadows_emerges_from_a_reflective_ornate_mirror._The_scene_is_dramatic_with_deep_inky_blacks_and_subtle_hints_of_dark_purple_and_blue_within_the_shadow_form._The_mirrors_surface_sho.jpg"

NPC_QUOTES = [
    "“Power has a price… lay your copies before the mirror, and let them vanish.”",
    "“Only by surrendering what you have… can you become what you seek.”",
    "“Do not mourn the cards you give. Their essence will live… through a stronger form.”",
    "“Reflection reveals potential. Sacrifice reveals truth.”",
    "“Bring me the duplicates. I will unmake them… and return to you something greater.”",
    "“Every upgrade is a grave. Are you ready to bury what you own?”",
    "“Let the mirror consume your excess. In return, it will sharpen your fate.”"
]

# --- UI Components ---
class MirrorView(View):
    def __init__(self, bot, user):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.add_item(LookButton(bot, user))
        self.add_item(LeaveButton())


class LookButton(Button):
    def __init__(self, bot, user):
        super().__init__(label="Look into the mirror", style=discord.ButtonStyle.primary)
        self.bot = bot
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ This is not your mirror.", ephemeral=True)
            return

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.card_id, c.base_name, c.name, c.rarity, uc.quantity,
                       c.health, c.attack, c.speed,
                       uc.health AS u_health, uc.attack AS u_attack, uc.speed AS u_speed
                FROM user_cards uc
                JOIN cards c ON c.card_id = uc.card_id
                WHERE uc.user_id = $1
            """, self.user.id)

        upgradable = []
        for row in rows:
            if row["rarity"] in UPGRADE_RULES and row["quantity"] >= UPGRADE_RULES[row["rarity"]]["copies"]:
                upgradable.append(row)

        if not upgradable:
            await interaction.response.edit_message(
                content="The mirror whispers: *You have nothing to offer me...*",
                embed=None, view=None
            )
            return

        options = [
            discord.SelectOption(
                label=f"{c['name']} ({c['rarity'].capitalize()})",
                description=f"Qty: {c['quantity']} → Upgrade to {UPGRADE_RULES[c['rarity']]['next'].capitalize()}",
                value=str(c["card_id"])
            )
            for c in upgradable[:25]
        ]

        select = UpgradeSelect(self.bot, self.user, upgradable, options)
        view = View(timeout=60)
        view.add_item(select)

        embed = discord.Embed(
            title="🌑 The Mirror Deepens",
            description="A figure of swirling shadows emerges from the glass...",
            color=discord.Color.dark_purple()
        )
        embed.set_image(url=MIRROR_IMAGE)

        await interaction.response.edit_message(embed=embed, view=view)


class LeaveButton(Button):
    def __init__(self):
        super().__init__(label="Leave the mirror behind", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="You turn away from the mirror.", embed=None, view=None)


class UpgradeSelect(Select):
    def __init__(self, bot, user, cards, options):
        super().__init__(placeholder="Choose a card to upgrade...", options=options, min_values=1, max_values=1)
        self.bot = bot
        self.user = user
        self.cards = {str(c["card_id"]): c for c in cards}

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("⚠️ This is not your mirror.", ephemeral=True)
            return

        card = self.cards[self.values[0]]
        rule = UPGRADE_RULES[card["rarity"]]
        next_rarity = rule["next"]

        async with self.bot.db.acquire() as conn:
            next_card = await conn.fetchrow("""
                SELECT * FROM cards WHERE base_name = $1 AND rarity = $2 LIMIT 1
            """, card["base_name"], next_rarity)

            if not next_card:
                await interaction.response.send_message("⚠️ No upgraded version found.", ephemeral=True)
                return

            old_entity = entity_from_db(card, {
                "health": card["u_health"], "attack": card["u_attack"], "speed": card["u_speed"]
            })
            new_entity = entity_from_db(next_card)

            async with conn.transaction():
                # Check bypass flag
                flags = await conn.fetchrow("SELECT bypass_upgrade FROM users WHERE user_id = $1", self.user.id)
                bypass = flags and flags["bypass_upgrade"]

                if not bypass:
                    # Normal cost + copies
                    await conn.execute("UPDATE users SET bloodcoins = bloodcoins - $1 WHERE user_id = $2",
                                       rule["cost"], self.user.id)
                    await conn.execute("UPDATE user_cards SET quantity = quantity - $1 WHERE user_id = $2 AND card_id = $3",
                                       rule["copies"], self.user.id, card["card_id"])

                # Always give upgraded card
                await conn.execute("""
                    INSERT INTO user_cards (user_id, card_id, quantity)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (user_id, card_id)
                    DO UPDATE SET quantity = user_cards.quantity + 1
                """, self.user.id, next_card["card_id"])

        old_stats = f"❤️ {old_entity.stats.health} | 🗡️ {old_entity.stats.attack} | ⚡ {old_entity.stats.speed}"
        new_stats = f"❤️ {new_entity.stats.health} | 🗡️ {new_entity.stats.attack} | ⚡ {new_entity.stats.speed}"
        delta = f"+❤️ {new_entity.stats.health - old_entity.stats.health} | " \
                f"+🗡️ {new_entity.stats.attack - old_entity.stats.attack} | " \
                f"+⚡ {new_entity.stats.speed - old_entity.stats.speed}"

        desc = f"Your **{card['name']}** has been consumed and reborn as **{next_card['name']}**!"
        if bypass:
            desc += "\n\n⚡ *Admin bypass active: no cost or copies consumed.*"

        embed = discord.Embed(
            title="✨ The Mirror Shifts...",
            description=desc,
            color=RARITY_COLORS.get(next_rarity, discord.Color.dark_gray())
        )
        embed.set_image(url=MIRROR_IMAGE)
        embed.add_field(name="Stats before", value=old_stats, inline=False)
        embed.add_field(name="Stats after", value=new_stats, inline=False)
        embed.add_field(name="Change", value=delta, inline=False)

        await interaction.response.edit_message(content=None, embed=embed, view=None)


# --- Cog ---
class UpgradeNPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="upgrade")
    async def upgrade(self, ctx):
        """Begin the NPC upgrade ritual."""
        quote = random.choice(NPC_QUOTES)
        embed = discord.Embed(
            title="🪞 The Mirror",
            description=quote,
            color=discord.Color.purple()
        )
        embed.set_image(url=NPC_IMAGE)

        view = MirrorView(self.bot, ctx.author)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(UpgradeNPC(bot))
