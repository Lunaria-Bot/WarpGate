import discord
from discord.ext import commands
from discord.ui import View, Button

# --- Quest Definitions ---
DAILY_QUESTS = [
    {"id": 1, "desc": "Upgrade 1 card", "target": 1, "reward_coins": 2000},
    {"id": 2, "desc": "Draw 10 times", "target": 10, "reward_coins": 500},
    {"id": 3, "desc": "Draw 5 times", "target": 5, "reward_coins": 250},
    {"id": 4, "desc": "Upgrade 2 cards", "target": 2, "reward_coins": 5000},
    {"id": 5, "desc": "Do !daily", "target": 1, "reward_coins": 500},
]

WEEKLY_QUESTS = [
    {"id": 6, "desc": "Do 5 !daily", "target": 5, "reward_coins": 15000},
    {"id": 7, "desc": "Draw 100 times", "target": 100, "reward_coins": 25000},
    {"id": 8, "desc": "Upgrade 10 cards", "target": 10, "reward_coins": 100000},
    {"id": 9, "desc": "Spend 10000 Bloodcoins", "target": 10000, "reward_item": "Random Epic Card"},
]

# --- Progress bar utility ---
def progress_bar(progress: int, target: int, length: int = 10) -> str:
    if target <= 0:
        return "N/A"
    filled = int(length * min(progress, target) / target)
    empty = length - filled
    return f"{'▰' * filled}{'▱' * empty} {progress}/{target}"

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

# --- Claim Button ---
class ClaimButton(Button):
    def __init__(self, quest, parent_view):
        super().__init__(label="🎁 Claim Reward", style=discord.ButtonStyle.success)
        self.quest = quest
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            await interaction.response.send_message("⚠️ This is not your quest menu.", ephemeral=True)
            return

        async with self.parent_view.bot.db.acquire() as conn:
            updated = await conn.execute("""
                UPDATE user_quests
                SET claimed = TRUE
                WHERE user_id = $1 AND quest_id = $2 AND completed = TRUE AND claimed = FALSE
            """, interaction.user.id, self.quest["id"])

            if updated == "UPDATE 1":
                if self.quest.get("reward_coins"):
                    await conn.execute(
                        "UPDATE users SET bloodcoins = bloodcoins + $1 WHERE user_id = $2",
                        self.quest["reward_coins"], interaction.user.id
                    )
                    reward_text = f"💰 {self.quest['reward_coins']} Bloodcoins"
                else:
                    reward_text = f"🎴 {self.quest['reward_item']}"
                    # TODO: Insert logic to grant the card reward

                await interaction.response.send_message(f"✅ You claimed your reward: {reward_text}", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ You cannot claim this quest yet.", ephemeral=True)

# --- Quest Menu View ---
class QuestView(View):
    def __init__(self, bot, author):
        super().__init__(timeout=120)
        self.bot = bot
        self.author = author

        daily_btn = Button(label="📅 Daily Quests", style=discord.ButtonStyle.primary)
        weekly_btn = Button(label="📆 Weekly Quests", style=discord.ButtonStyle.success)

        daily_btn.callback = self.show_daily
        weekly_btn.callback = self.show_weekly

        self.add_item(daily_btn)
        self.add_item(weekly_btn)

    async def show_daily(self, interaction: discord.Interaction):
        await self.show_quests(interaction, DAILY_QUESTS, "📅 Daily Quests", discord.Color.blurple())

    async def show_weekly(self, interaction: discord.Interaction):
        await self.show_quests(interaction, WEEKLY_QUESTS, "📆 Weekly Quests", discord.Color.gold())

    async def show_quests(self, interaction, quest_list, title, color):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ Not your quest menu.", ephemeral=True)
            return

        embed = discord.Embed(title=title, description="Your current challenges:", color=color)

        async with self.bot.db.acquire() as conn:
            for q in quest_list:
                quest = await conn.fetchrow("""
                    SELECT progress, completed, claimed
                    FROM user_quests
                    WHERE user_id = $1 AND quest_id = $2
                """, interaction.user.id, q["id"])

                if quest:
                    bar = progress_bar(quest["progress"], q["target"])
                    status = "✅ Claimed" if quest["claimed"] else ("🏆 Completed" if quest["completed"] else bar)
                else:
                    bar = progress_bar(0, q["target"])
                    status = bar

                reward = f"💰 {q['reward_coins']} Bloodcoins" if q.get("reward_coins") else f"🎴 {q['reward_item']}"
                embed.add_field(name=q["desc"], value=f"Progress: {status}\nReward: {reward}", inline=False)

        embed.set_thumbnail(url=self.author.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

# --- Cog ---
class Quests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="quest", aliases=["quests"])
    async def quest(self, ctx):
        """Open the Quest Master menu with Daily/Weekly quests."""
        embed = discord.Embed(
            title="🧙 Quest Master",
            description="Welcome adventurer! Choose your quests:",
            color=discord.Color.purple()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1428075046454431784/1428075092520468620/image.png?ex=68f12e12&is=68efdc92&hm=7c4f25bc0659da9d27328a2ba810b6e5ed68395e3673eab9d1499bab32ca392f&")  # Replace with your NPC image

        view = QuestView(self.bot, ctx.author)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Quests(bot))
