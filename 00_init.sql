-- 00_init.sql
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT NOT NULL,
    avatar_id TEXT,
    faction_id TEXT,
    level INT NOT NULL DEFAULT 1,
    badges JSONB NOT NULL DEFAULT '[]',
    equipment JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS factions (
    faction_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS avatars (
    avatar_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    image_url TEXT
);

CREATE TABLE IF NOT EXISTS currencies (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    blood_coins BIGINT NOT NULL DEFAULT 0,
    noble_coins BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rarity TEXT NOT NULL CHECK (rarity IN ('COMMON','RARE','EPIC','LEGENDARY')),
    faction_id TEXT,
    drop_weight INT NOT NULL DEFAULT 1, -- pour le tirage pondéré
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS user_cards (
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    card_id TEXT REFERENCES cards(card_id) ON DELETE CASCADE,
    qty INT NOT NULL DEFAULT 1,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, card_id)
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id BIGSERIAL PRIMARY KEY,
    initiator_id BIGINT NOT NULL,
    recipient_id BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN','CONFIRMED_INITIATOR','CONFIRMED_RECIPIENT','COMPLETED','CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trade_items (
    trade_id BIGINT REFERENCES trades(trade_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    item_type TEXT NOT NULL CHECK (item_type IN ('CARD','BLOOD_COINS','NOBLE_COINS')),
    card_id TEXT,
    amount BIGINT,
    PRIMARY KEY (trade_id, user_id, item_type, COALESCE(card_id,''))
);

-- Seed minimal
INSERT INTO factions (faction_id, name, description) VALUES
    ('ASHEN','Ashen Order','Guerriers austères'), 
    ('VERDANT','Verdant Pact','Protecteurs de la nature'),
    ('AZURE','Azure Syndicate','Mages érudits')
ON CONFLICT DO NOTHING;

INSERT INTO avatars (avatar_id, name, image_url) VALUES
    ('AV1','Rogue','https://example/av1.png'),
    ('AV2','Knight','https://example/av2.png'),
    ('AV3','Mage','https://example/av3.png')
ON CONFLICT DO NOTHING;

INSERT INTO cards (card_id, name, rarity, faction_id, drop_weight) VALUES
    ('C001','Ashen Scout','COMMON','ASHEN', 50),
    ('C002','Verdant Sapling','COMMON','VERDANT', 50),
    ('C003','Azure Spark','COMMON','AZURE', 50),
    ('C101','Ashen Captain','RARE','ASHEN', 10),
    ('C201','Verdant Guardian','EPIC','VERDANT', 4),
    ('C301','Azure Archmage','LEGENDARY','AZURE', 1)
ON CONFLICT DO NOTHING;
