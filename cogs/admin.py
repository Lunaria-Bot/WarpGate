import discord
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Helper: admin check ---
    def admin_only():
        async def predicate(ctx):
            return ctx.author.guild_permissions.administrator
        return commands.check(predicate)

    # --- Currency management ---
    @commands.command(name="addblood")
    @admin_only()
    async def add_bloodcoins(self, ctx, member: discord.Member, amount: int):
        """Add BloodCoins to a player."""
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET bloodcoins = bloodcoins + $1
                WHERE user_id = $2
            """, amount, member.id)
        await ctx.send(f"✅ Added {amount} BloodCoins to {member.display_name}.")

    @commands.command(name="addnoble")
    @admin_only()
    async def add_noblecoins(self, ctx, member: discord.Member, amount: int):
        """Add NobleCoins to a player."""
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET noble_coins = noble_coins + $1
                WHERE user_id = $2
            """, amount, member.id)
        await ctx.send(f"✅ Added {amount} NobleCoins to {member.display_name}.")

    # --- Bypass flags ---
    @commands.command(name="bypass_upgrade")
    @admin_only()
    async def bypass_upgrade(self, ctx, member: discord.Member, enabled: bool = True):
        """Toggle bypassing upgrade cost for a player."""
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET bypass_upgrade = $1
                WHERE user_id = $2
            """, enabled, member.id)
        await ctx.send(f"⚙️ Upgrade cost bypass for {member.display_name}: {enabled}")

    @commands.command(name="bypass_draw")
    @admin_only()
    async def bypass_draw(self, ctx, member: discord.Member, enabled: bool = True):
        """Toggle bypassing draw cooldown for a player."""
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET bypass_draw = $1
                WHERE user_id = $2
            """, enabled, member.id)
        await ctx.send(f"⚙️ Draw cooldown bypass for {member.display_name}: {enabled}")

    # --- Ban / Unban ---
    @commands.command(name="banplayer")
    @admin_only()
    async def ban_player(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Ban a player (lock their account, prevent draw)."""
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET banned = TRUE, ban_reason = $1
                WHERE user_id = $2
            """, reason, member.id)
        await ctx.send(f"⛔ {member.display_name} has been banned. Reason: {reason}")

    @commands.command(name="unbanplayer")
    @admin_only()
    async def unban_player(self, ctx, member: discord.Member):
        """Unban a player."""
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET banned = FALSE, ban_reason = NULL
                WHERE user_id = $1
            """, member.id)
        await ctx.send(f"✅ {member.display_name} has been unbanned.")

    # --- Show profile of another user ---
    @commands.command(name="showprofile")
    @admin_only()
    async def show_profile(self, ctx, member: discord.Member):
        """Show another user's profile (admin view)."""
        profile_cog = self.bot.get_cog("Profile")
        if not profile_cog:
            await ctx.send("⚠️ Profile system not loaded.")
            return
        await profile_cog.profile(ctx, member=member)

    # --- Give a specific card ---
    @commands.command(name="givecard")
    @admin_only()
    async def give_card(self, ctx, member: discord.Member, rarity: str, *, card_name: str):
        """
        Give a specific card to a player.
        Usage: !givecard @user <rarity> <card name>
        Example: !givecard @Kyriun epic Dark Knight
        """
        async with self.bot.db.acquire() as conn:
            # Find the card by name and rarity
            card = await conn.fetchrow("""
                SELECT card_id, name, rarity
                FROM cards
                WHERE (LOWER(base_name) = LOWER($1) OR LOWER(name) = LOWER($1))
                  AND rarity ILIKE $2
                LIMIT 1
            """, card_name, rarity)

            if not card:
                await ctx.send(f"⚠️ No card found with name '{card_name}' and rarity '{rarity}'.")
                return

            # Insert or increment in user_cards
            await conn.execute("""
                INSERT INTO user_cards (user_id, card_id, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (user_id, card_id)
                DO UPDATE SET quantity = user_cards.quantity + 1
            """, member.id, card["card_id"])

        await ctx.send(f"✅ Gave **{card['name']}** ({card['rarity'].capitalize()}) to {member.display_name}.")


async def setup(bot):
    await bot.add_cog(Admin(bot))
