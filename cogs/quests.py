import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import datetime, asyncio

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
    filled = int(length * min(progress, target) / target)
    return f"{'▰'*filled}{'▱'*(length-filled)} {progress}/{target}"

# --- Claim Button ---
class ClaimButton(Button):
    def __init__(self, quest, parent_view):
        super().__init__(label="🎁 Claim Reward", style=discord.ButtonStyle.success)
        self.quest = quest
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.author:
            await interaction.response.send_message("⚠️ Not your quest menu.", ephemeral=True)
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
                await interaction.response.send_message(f"✅ You claimed: {reward_text}", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ Cannot claim yet.", ephemeral=True)

# --- Quest Menu View ---
class QuestView(View):
    def __init__(self, bot, author):
        super().__init__(timeout=120)
        self.bot, self.author = bot, author
        daily_btn = Button(label="📅 Daily Quests", style=discord.ButtonStyle.primary)
        weekly_btn = Button(label="📆 Weekly Quests", style=discord.ButtonStyle.success)
        daily_btn.callback = self.show_daily
        weekly_btn.callback = self.show_weekly
        self.add_item(daily_btn); self.add_item(weekly_btn)

    async def show_daily(self, i): await self.show_quests(i, DAILY_QUESTS, "📅 Daily Quests", discord.Color.blurple())
    async def show_weekly(self, i): await self.show_quests(i, WEEKLY_QUESTS, "📆 Weekly Quests", discord.Color.gold())

    async def show_quests(self, interaction, quest_list, title, color):
        if interaction.user != self.author:
            await interaction.response.send_message("⚠️ Not your quest menu.", ephemeral=True); return
        embed = discord.Embed(title=title, description="Your current challenges:", color=color)
        async with self.bot.db.acquire() as conn:
            for q in quest_list:
                quest = await conn.fetchrow("SELECT progress, completed, claimed FROM user_quests WHERE user_id=$1 AND quest_id=$2", interaction.user.id, q["id"])
                if quest:
                    bar = progress_bar(quest["progress"], q["target"])
                    status = "✅ Claimed" if quest["claimed"] else ("🏆 Completed" if quest["completed"] else bar)
                else:
                    status = progress_bar(0, q["target"])
                reward = f"💰 {q['reward_coins']} Bloodcoins" if q.get("reward_coins") else f"🎴 {q['reward_item']}"
                embed.add_field(name=q["desc"], value=f"Progress: {status}\nReward: {reward}", inline=False)
        embed.set_image(url="https://i.imgur.com/8hQ6YkR.png")  # NPC art
        await interaction.response.edit_message(embed=embed, view=self)

# --- Cog with resets ---
class Quests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_reset.start()
        self.weekly_reset.start()

    def cog_unload(self):
        self.daily_reset.cancel()
        self.weekly_reset.cancel()

    @tasks.loop(hours=24)
    async def daily_reset(self):
        now = datetime.datetime.utcnow()
        target = datetime.datetime.combine(now.date(), datetime.time.min)
        if now > target: target += datetime.timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        async with self.bot.db.acquire() as conn:
            await conn.execute("DELETE FROM user_quests WHERE quest_id IN (SELECT quest_id FROM quest_templates WHERE type='daily')")
            await conn.execute("""
                INSERT INTO user_quests (user_id, quest_id)
                SELECT u.user_id, q.quest_id
                FROM users u CROSS JOIN quest_templates q
                WHERE q.type='daily'
            """)

    @tasks.loop(hours=168)
    async def weekly_reset(self):
        now = datetime.datetime.utcnow()
        days_ahead = (7 - now.weekday()) % 7
        target = datetime.datetime.combine(now.date(), datetime.time.min) + datetime.timedelta(days=days_ahead)
        if now > target: target += datetime.timedelta(days=7)
        await asyncio.sleep((target - now).total_seconds())
        async with self.bot.db.acquire() as conn:
            await conn.execute("DELETE FROM user_quests WHERE quest_id IN (SELECT quest_id FROM quest_templates WHERE type='weekly')")
            await conn.execute("""
                INSERT INTO user_quests (user_id, quest_id)
                SELECT u.user_id, q.quest_id
                FROM users u CROSS JOIN quest_templates q
                WHERE q.type='weekly'
            """)

    @commands.command(name="quest", aliases=["quests"])
    async def quest(self, ctx):
        embed = discord.Embed(title="🧙 Quest Master", description="Welcome adventurer! Choose your quests:", color=discord.Color.purple())
        embed.set_image(url="https://i.imgur.com/8hQ6YkR.png")
        await ctx.send(embed=embed, view=QuestView(self.bot, ctx.author))

async def setup(bot): await bot.add_cog(Quests(bot))
