import discord
from discord.ext import commands

CARDS_PER_PAGE = 5
RARITIES = ["All", "Common", "Rare", "Epic", "Legendary"]

class CardView(discord.ui.View):
    def __init__(self, ctx, pool, rarity="All", page=0, detail_mode=False, cards_cache=None):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.pool = pool
        self.rarity = rarity
        self.page = page
        self.detail_mode = detail_mode
        self.cards_cache = cards_cache or []
        self.page_cards = []
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
        if self.detail_mode:
            # In detail mode, embed is set by CardSelect callback
            return self.detail_embed

        self.cards_cache = await self.fetch_cards()
        start = self.page * CARDS_PER_PAGE
        end = start + CARDS_PER_PAGE
        self.page_cards = self.cards_cache[start:end]

        embed = discord.Embed(
            title=f"Available Cards ({self.rarity})",
            description=f"Page {self.page+1}/{max(1, (len(self.cards_cache)-1)//CARDS_PER_PAGE+1)}",
            color=discord.Color.blurple()
        )
        if not self.page_cards:
            embed.add_field(name="No cards", value="No cards available for this filter.")
        else:
            for c in self.page_cards:
                embed.add_field(
                    name=f"#{c['id']} {c['name']}",
                    value=f"Rarity: {c['rarity'].capitalize()}",
                    inline=False
                )
        return embed

    def update_items(self):
        self.clear_items()
        if self.detail_mode:
            self.add_item(BackToListButton(self))
        else:
            self.add_item(RaritySelect(self))
            self.add_item(PrevButton(self))
            self.add_item(NextButton(self))
            self.add_item(MainMenuButton(self))
            if self.page_cards:
                self.add_item(CardSelect(self, self.page_cards))

class RaritySelect(discord.ui.Select):
    def __init__(self, view):
        options = [discord.SelectOption(label=r, value=r) for r in RARITIES]
        super().__init__(placeholder="Filter by rarity...", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.rarity = self.values[0]
        self.view_ref.page = 0
        self.view_ref.detail_mode = False
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
        self.view_ref.detail_mode = False
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
        self.view_ref.detail_mode = False
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
        self.view_ref.detail_mode = False
        self.view_ref.update_items()
        await interaction.response.edit_message(
            embed=await self.view_ref.get_embed(), view=self.view_ref
        )

class CardSelect(discord.ui.Select):
    def __init__(self, view, cards):
        options = [
            discord.SelectOption(label=f"#{c['id']} {c['name']}", value=str(c['id']))
            for c in cards
        ]
        super().__init__(placeholder="Select a card to view details…", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        card_id = int(self.values[0])
        async with self.view_ref.pool.acquire() as conn:
            card = await conn.fetchrow(
                "SELECT id, name, rarity, description, image_url FROM cards WHERE id=$1",
                card_id
            )
        if not card:
            await interaction.response.send_message("❌ Card not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{card['name']} (#{card['id']})",
            description=card["description"] or "—",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Rarity", value=card["rarity"].capitalize(), inline=True)
        if card["image_url"]:
            embed.set_image(url=card["image_url"])

        self.view_ref.detail_mode = True
        self.view_ref.detail_embed = embed
        self.view_ref.update_items()
        await interaction.response.edit_message(embed=embed, view=self.view_ref)

class BackToListButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬅️ Back to list")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.detail_mode = False
        self.view_ref.update_items()
        await interaction.response.edit_message(
            embed=await self.view_ref.get_embed(), view=self.view_ref
        )

class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="view")
    async def view_cards(self, ctx):
        """View cards with rarity filter, pagination, and detail view"""
        view = CardView(ctx, self.bot.db)
        await ctx.send(embed=await view.get_embed(), view=view)

async def setup(bot):
    await bot.add_cog(Cards(bot))
