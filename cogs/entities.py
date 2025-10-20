import discord

# --- Base stats by form (fallback if nothing in DB) ---
FORM_BASE_STATS = {
    "base":      {"health": 100, "attack": 10, "speed": 10},
    "awakened":  {"health": 150, "attack": 20, "speed": 15},
    "event":     {"health": 120, "attack": 15, "speed": 20},
}

FORM_EMOJIS = {
    "base": "🟦",
    "awakened": "✨",
    "event": "🎉"
}

FORM_COLORS = {
    "base": discord.Color.blue(),
    "awakened": discord.Color.gold(),
    "event": discord.Color.magenta()
}

class Stats:
    def __init__(self, health: int, attack: int, speed: int):
        self.health = health
        self.attack = attack
        self.speed = speed

    def __repr__(self):
        return f"❤️ {self.health} | 🗡️ {self.attack} | 💨 {self.speed}"

class Entity:
    def __init__(self, name: str, form: str = "base",
                 image_url: str = None, description: str = None,
                 override_stats: dict = None):
        """
        - name: entity name (card or monster)
        - form: base, awakened, event
        - image_url: associated image
        - description: descriptive text
        - override_stats: optional dict to override default stats
        """
        base = FORM_BASE_STATS.get(form.lower(), FORM_BASE_STATS["base"])
        if override_stats:
            base = {**base, **override_stats}
        self.name = name
        self.form = form
        self.stats = Stats(**base)
        self.image_url = image_url
        self.description = description or ""

    def is_alive(self) -> bool:
        return self.stats.health > 0

    def attack_target(self, target: "Entity") -> int:
        damage = self.stats.attack
        target.stats.health = max(0, target.stats.health - damage)
        return damage

    def to_embed(self, title_prefix="✨ You drew:"):
        embed = discord.Embed(
            title=f"{title_prefix} {FORM_EMOJIS.get(self.form, '')} {self.name}",
            description=self.description,
            color=FORM_COLORS.get(self.form, discord.Color.dark_gray())
        )
        embed.add_field(name="Form", value=self.form.capitalize(), inline=True)
        embed.add_field(name="Stats", value=str(self.stats), inline=False)
        if self.image_url:
            embed.set_thumbnail(url=self.image_url)
        return embed

# --- Factory to build an Entity from DB rows ---
def entity_from_db(card_row, user_card_row=None):
    """
    Build an Entity from a SQL row.
    Stat priority:
    1. user_cards (if defined)
    2. cards (if defined)
    3. FORM_BASE_STATS
    """
    override_stats = {}

    # From user_cards
    if user_card_row:
        if user_card_row.get("health") is not None:
            override_stats["health"] = user_card_row["health"]
        if user_card_row.get("attack") is not None:
            override_stats["attack"] = user_card_row["attack"]
        if user_card_row.get("speed") is not None:
            override_stats["speed"] = user_card_row["speed"]

    # From cards
    if not override_stats:
        if card_row.get("health") is not None:
            override_stats["health"] = card_row["health"]
        if card_row.get("attack") is not None:
            override_stats["attack"] = card_row["attack"]
        if card_row.get("speed") is not None:
            override_stats["speed"] = card_row["speed"]

    return Entity(
        name=card_row.get("character_name") or card_row.get("name"),
        form=card_row.get("form", "base"),
        image_url=card_row.get("image_url"),
        description=card_row.get("description"),
        override_stats=override_stats if override_stats else None
    )
