import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.db import db_transaction
from cogs.entities import entity_from_db

class TeamView(View):
    def __init__(self, entities: list, author: discord.User):
        super().__init__(timeout=60)
        self.entities = entities
        self.index = 0
        self.author = author
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=None)

    async def update_embed(self, interaction: discord.Interaction):
        entity = self.entities[self.index]
        embed = entity.to_embed(title_prefix=f"📦 Slot {self.index + 1}:")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index - 1) % len(self.entities)
        await self.update_embed(interaction)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index + 1) % len(self.entities)
        await self.update_embed(interaction)

class Team(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="teamset")
    async def set_team(self, ctx, *codes: str):
        if not codes:
            return await ctx.send("❌ You must provide at least one card code (e.g. `GojoSatoru-base`).")

        discord_id = str(ctx.author.id)

        async with db_transaction(self.bot.db) as conn:
            user_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not user_id:
                return await ctx.send("⚠️ You don't have a profile yet. Use `wregister`.")

            owned = await conn.fetch("""
                SELECT uc.card_id, c.code
                FROM user_cards uc
                JOIN cards c ON c.id = uc.card_id
                WHERE uc.user_id = $1
            """, user_id)

            code_map = {row["code"].lower(): row["card_id"] for row in owned}
            card_ids = []

            for code in codes:
                normalized = code.lower().strip()
                if normalized not in code_map:
                    return await ctx.send(f"❌ You don't own a card with code `{code}`.")
                card_ids.append(code_map[normalized])

            await conn.execute("DELETE FROM player_team WHERE user_id = $1", user_id)

            for slot, card_id in enumerate(card_ids, start=1):
                await conn.execute("""
                    INSERT INTO player_team (user_id, card_id, slot)
                    VALUES ($1, $2, $3)
                """, user_id, card_id, slot)

        await ctx.send(f"✅ Your team has been updated with {len(card_ids)} card(s).")

    @commands.command(name="team")
    async def show_team(self, ctx):
        discord_id = str(ctx.author.id)

        async with db_transaction(self.bot.db) as conn:
            user_id = await conn.fetchval("SELECT id FROM players WHERE discord_id = $1", discord_id)
            if not user_id:
                return await ctx.send("⚠️ You don't have a profile yet. Use `wregister`.")

            rows = await conn.fetch("""
                SELECT pt.slot, pt.is_captain,
                       c.id AS card_id, c.character_name, c.form, c.image_url, c.description,
                       uc.quantity, uc.xp, uc.health, uc.attack, uc.speed
                FROM player_team pt
                JOIN user_cards uc ON uc.card_id = pt.card_id AND uc.user_id = pt.user_id
                JOIN cards c ON c.id = pt.card_id
                WHERE pt.user_id = $1
                ORDER BY pt.slot
            """, user_id)

        if not rows:
            return await ctx.send("ℹ️ Your team is empty. Use `teamset` to define it.")

        entities = [entity_from_db(card_row=row, user_card_row=row) for row in rows]
        view = TeamView(entities, ctx.author)
        embed = entities[0].to_embed(title_prefix="📦 Slot 1:")
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

async def setup(bot):
    await bot.add_cog(Team(bot))
