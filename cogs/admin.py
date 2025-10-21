import discord
from discord.ext import commands
from models.card import Card
from models.user_card import UserCard
from sqlalchemy.future import select

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
        discord_id = str(member.id)
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE players
                SET bloodcoins = bloodcoins + $1
                WHERE discord_id = $2
            """, amount, discord_id)
        await ctx.send(f"✅ Added {amount} BloodCoins to {member.display_name}.")

    @commands.command(name="addnoble")
    @admin_only()
    async def add_noblecoins(self, ctx, member: discord.Member, amount: int):
        discord_id = str(member.id)
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE players
                SET noblecoins = noblecoins + $1
                WHERE discord_id = $2
            """, amount, discord_id)
        await ctx.send(f"✅ Added {amount} NobleCoins to {member.display_name}.")

    # --- Bypass flags ---
    @commands.command(name="bypass_upgrade")
    @admin_only()
    async def bypass_upgrade(self, ctx, member: discord.Member, enabled: bool = True):
        discord_id = str(member.id)
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE players
                SET bypass_upgrade = $1
                WHERE discord_id = $2
            """, enabled, discord_id)
        await ctx.send(f"⚙️ Upgrade cost bypass for {member.display_name}: {enabled}")

    @commands.command(name="bypass_draw")
    @admin_only()
    async def bypass_draw(self, ctx, member: discord.Member, enabled: bool = True):
        discord_id = str(member.id)
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE players
                SET bypass_draw = $1
                WHERE discord_id = $2
            """, enabled, discord_id)
        await ctx.send(f"⚙️ Draw cooldown bypass for {member.display_name}: {enabled}")

    # --- Ban / Unban ---
    @commands.command(name="banplayer")
    @admin_only()
    async def ban_player(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        discord_id = str(member.id)
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE players
                SET banned = TRUE, ban_reason = $1
                WHERE discord_id = $2
            """, reason, discord_id)
        await ctx.send(f"⛔ {member.display_name} has been banned. Reason: {reason}")

    @commands.command(name="unbanplayer")
    @admin_only()
    async def unban_player(self, ctx, member: discord.Member):
        discord_id = str(member.id)
        async with self.bot.db.acquire() as conn:
            await conn.execute("""
                UPDATE players
                SET banned = FALSE, ban_reason = NULL
                WHERE discord_id = $1
            """, discord_id)
        await ctx.send(f"✅ {member.display_name} has been unbanned.")

    # --- Show profile of another user ---
    @commands.command(name="showprofile")
    @admin_only()
    async def show_profile(self, ctx, member: discord.Member):
        profile_cog = self.bot.get_cog("Profile")
        if not profile_cog:
            await ctx.send("⚠️ Profile system not loaded.")
            return
        await profile_cog.profile(ctx, member=member)

    # --- Give a specific card ---
    @commands.command(name="givecard")
    @admin_only()
    async def give_card(self, ctx, member: discord.Member, form: str, *, character_name: str):
        """
        Give a specific card to a player.
        Usage: mgivecard @user <form> <character name>
        Example: mgivecard @Kyriun awakened Dark Knight
        """
        form = form.lower()
        if form not in ["base", "awakened", "event"]:
            await ctx.send("⚠️ Invalid form. Use: base, awakened, or event.")
            return

        async with self.bot.db.begin() as session:
            result = await session.execute(
                select(Card).where(
                    Card.character_name.ilike(character_name),
                    Card.form == form
                ).limit(1)
            )
            card = result.scalar()

            if not card:
                await ctx.send(f"⚠️ No card found with name '{character_name}' and form '{form}'.")
                return

            session.add(UserCard(discord_id=str(member.id), card_id=card.id))
            await session.commit()

        await ctx.send(f"✅ Gave **{card.character_name}** ({form}) to {member.display_name}.")

async def setup(bot):
    await bot.add_cog(Admin(bot))
