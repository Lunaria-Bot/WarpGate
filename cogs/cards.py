import discord
from discord.ext import commands
from db import init_db

CARDS_PER_PAGE = 5
RARITIES = ["All", "Common", "Rare", "Epic", "Legendary"]

class CardView(discord.ui.View):
    def __init__(self, ctx, pool, rarity="All", page=0):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.pool = pool
        self.rarity = rarity
        self.page = page
        self.update_items()

    async def fetch_cards(self):
        async with self.pool.acquire() as conn:
            if self.rarity == "All":
                return await conn.fetch("SELECT id, name, rarity FROM cards ORDER BY id ASC")
            return await conn.fetch(
                "SELECT id, name, rarity FROM cards WHERE rarity=$1 ORDER BY id ASC",
                self.rarity.lower()
            )

    async def get_embed(self):
        cards = await self.fetch_cards()
        start = self.page * CARDS_PER_PAGE
        end = start + CARDS_PER_PAGE
        page_cards = cards[start:end]

        embed = discord.Embed(
            title=f"Available Cards ({self.rarity})",
            description=f"Page {self.page+1}/{max(1, (len(cards)-1)//CARDS_PER_PAGE+1)}",
            color=discord.Color.blurple()
        )
        if not page_cards:
            embed.add_field(name="No cards", value="No cards available for this filter.")
        else:
            for c in page_cards:
                embed.add_field(
                    name=f"#{c['id']} {c['name']}",
                    value=f"Rarity: {c['rarity'].capitalize()}",
                    inline=False
                )
        return embed

    def update_items(self):
        self.clear_items()
        self.add_item(RaritySelect(self))
        self.add_item(PrevButton(self))
        self.add_item(NextButton(self))
        self.add_item(MainMenuButton(self))

class RaritySelect(discord.ui.Select):
    def __init__(self, view):
        options = [discord.SelectOption(label=r, value=r) for r in RARITIES]
        super().__init__(placeholder="Filter by rarity...", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.rarity = self.values[0]
        self.view_ref.page = 0
        self.view_ref.update_items()
        await interaction.response.edit_message(
            embed=await self.view_ref.get_embed(), view=self.view_ref
        )

class PrevButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="◀️")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.page > 0:
            self.view_ref.page -= 1
        self.view_ref.update_items()
        await interaction.response.edit_message(
            embed=await self.view_ref.get_embed(), view=self.view_ref
        )

class NextButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="▶️")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        cards = await self.view_ref.fetch_cards()
        max_page = (len(cards)-1)//CARDS_PER_PAGE
        if self.view_ref.page < max_page:
            self.view_ref.page += 1
        self.view_ref.update_items()
        await interaction.response.edit_message(
            embed=await self.view_ref.get_embed(), view=self.view_ref
        )

class MainMenuButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(style=discord.ButtonStyle.primary, label="Main Menu")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.rarity = "All"
        self.view_ref.page = 0
        self.view_ref.update_items()
        await interaction.response.edit_message(
            embed=await self.view_ref.get_embed(), view=self.view_ref
        )

class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = db.pool  # WarpGate’s db.py exposes a global pool

    @commands.command(name="view")
    async def view_cards(self, ctx):
        """View cards with rarity filter and pagination"""
        view = CardView(ctx, self.pool)
        await ctx.send(embed=await view.get_embed(), view=view)

async def setup(bot):
    await bot.add_cog(Cards(bot))
