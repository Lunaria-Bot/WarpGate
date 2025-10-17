import discord

# --- Base stats par rareté (fallback si rien en DB) ---
RARITY_BASE_STATS = {
    "common":    {"health": 10, "attack": 5,  "speed": 5},
    "rare":      {"health": 20, "attack": 8,  "speed": 7},
    "epic":      {"health": 35, "attack": 12, "speed": 9},
    "legendary": {"health": 50, "attack": 20, "speed": 12},
}

class Stats:
    def __init__(self, health: int, attack: int, speed: int):
        self.health = health
        self.attack = attack
        self.speed = speed

    def __repr__(self):
        return f"❤️ {self.health} | 🗡️ {self.attack} | ⚡ {self.speed}"


class Entity:
    def __init__(self, name: str, rarity: str = "common", 
                 image_url: str = None, description: str = None,
                 override_stats: dict = None):
        """
        - name: nom de l'entité (carte ou monstre)
        - rarity: rareté (common, rare, epic, legendary)
        - image_url: image associée
        - description: texte descriptif
        - override_stats: dict optionnel pour remplacer les stats par défaut
        """
        base = RARITY_BASE_STATS.get(rarity.lower(), RARITY_BASE_STATS["common"])
        if override_stats:
            base = {**base, **override_stats}
        self.name = name
        self.rarity = rarity
        self.stats = Stats(**base)
        self.image_url = image_url
        self.description = description or ""

    def is_alive(self) -> bool:
        return self.stats.health > 0

    def attack_target(self, target: "Entity") -> int:
        """Inflige des dégâts à une autre entité."""
        damage = self.stats.attack
        target.stats.health = max(0, target.stats.health - damage)
        return damage

    def to_embed(self, title_prefix="✨ You drew:"):
        embed = discord.Embed(
            title=f"{title_prefix} {self.name}",
            description=self.description,
            color=discord.Color.dark_gray()
        )
        embed.add_field(name="Rarity", value=self.rarity.capitalize(), inline=True)
        embed.add_field(name="Stats", value=str(self.stats), inline=False)
        if self.image_url:
            embed.set_thumbnail(url=self.image_url)
        return embed


# --- Fabrique d'entité depuis la DB ---
def entity_from_db(card_row, user_card_row=None):
    """
    Construit une Entity à partir d'une ligne SQL.
    Priorité des stats :
    1. user_cards (si défini)
    2. cards (si défini)
    3. RARITY_BASE_STATS
    """
    override_stats = {}

    # Niveau user_cards (si fourni)
    if user_card_row:
        if user_card_row.get("health") is not None:
            override_stats["health"] = user_card_row["health"]
        if user_card_row.get("attack") is not None:
            override_stats["attack"] = user_card_row["attack"]
        if user_card_row.get("speed") is not None:
            override_stats["speed"] = user_card_row["speed"]

    # Niveau cards
    if not override_stats:
        if card_row.get("health") is not None:
            override_stats["health"] = card_row["health"]
        if card_row.get("attack") is not None:
            override_stats["attack"] = card_row["attack"]
        if card_row.get("speed") is not None:
            override_stats["speed"] = card_row["speed"]

    return Entity(
        card_row["name"],
        rarity=card_row["rarity"],
        image_url=card_row.get("image_url"),
        description=card_row.get("description"),
        override_stats=override_stats if override_stats else None
    )
