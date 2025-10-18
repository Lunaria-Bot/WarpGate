async def add_xp(bot, user_id: int, amount: int):
    async with bot.db.acquire() as conn:
        profile = await conn.fetchrow(
            "SELECT level, xp, xp_next FROM users WHERE user_id=$1", user_id
        )
        if not profile:
            return False, None

        new_xp = profile["xp"] + amount
        level = profile["level"]
        xp_next = profile["xp_next"]

        leveled_up = False
        while new_xp >= xp_next:
            new_xp -= xp_next
            level += 1
            xp_next = int(xp_next * 1.2)  # progression exponentielle
            leveled_up = True

        await conn.execute("""
            UPDATE users
            SET xp=$1, level=$2, xp_next=$3
            WHERE user_id=$4
        """, new_xp, level, xp_next, user_id)

    return leveled_up, level
