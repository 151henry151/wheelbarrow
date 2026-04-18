-- Wheelbarrow MMO schema — v0.5.0
-- World content is generated at runtime by server/game/world_gen.py on first startup.

CREATE TABLE IF NOT EXISTS players (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    username          VARCHAR(32) UNIQUE NOT NULL,
    password_hash     VARCHAR(128),
    coins             INT DEFAULT 0,
    x                 DOUBLE DEFAULT 500,
    y                 DOUBLE DEFAULT 500,
    angle             DOUBLE DEFAULT 1.5707963267948966,
    bucket            JSON DEFAULT '{}',
    bucket_cap        INT DEFAULT 10,
    pocket            JSON DEFAULT '{}',
    wb_paint          FLOAT DEFAULT 100,
    wb_tire           FLOAT DEFAULT 100,
    wb_handle         FLOAT DEFAULT 100,
    flat_tire         TINYINT DEFAULT 0,
    wb_barrow         FLOAT DEFAULT 100,
    wb_bucket_level   TINYINT DEFAULT 1,
    wb_tire_level     TINYINT DEFAULT 1,
    wb_handle_level   TINYINT DEFAULT 1,
    wb_barrow_level   TINYINT DEFAULT 1,
    last_seen         DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_nodes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    x               INT NOT NULL,
    y               INT NOT NULL,
    node_type       VARCHAR(32) NOT NULL,
    current_amount  FLOAT DEFAULT 0,
    max_amount      FLOAT NOT NULL,
    replenish_rate  FLOAT NOT NULL,
    tree_variant    TINYINT UNSIGNED NOT NULL DEFAULT 0,
    last_tick       DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_position (x, y)
);

-- Towns: organically shaped zones (defined as center + polygon boundary points)
CREATE TABLE IF NOT EXISTS towns (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(64) NOT NULL,        -- procedurally generated
    custom_name     VARCHAR(64) DEFAULT NULL,    -- set by founder (once)
    center_x        INT NOT NULL,
    center_y        INT NOT NULL,
    -- Polygon boundary: JSON array of {x,y} points defining the irregular border
    boundary        JSON NOT NULL,
    -- Clustered NPC market + shops (one set per town), JSON object with market/seed_shop/general_store/repair_shop → [x,y]
    npc_district    JSON DEFAULT NULL,
    founder_id      INT DEFAULT NULL,
    leader_id       INT DEFAULT NULL,
    tax_rate        FLOAT DEFAULT 0,             -- 0.0–0.30
    treasury        INT DEFAULT 0,
    hall_built      TINYINT DEFAULT 0,
    next_election_at DATETIME DEFAULT NULL,
    FOREIGN KEY (founder_id) REFERENCES players(id),
    FOREIGN KEY (leader_id)  REFERENCES players(id)
);

-- Pre-generated variable-size land parcels scattered across the world.
-- NULL owner_id = available for purchase.
CREATE TABLE IF NOT EXISTS world_parcels (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    x            INT NOT NULL,
    y            INT NOT NULL,
    w            INT NOT NULL,
    h            INT NOT NULL,
    price        INT NOT NULL,
    town_id      INT DEFAULT NULL,
    owner_id     INT DEFAULT NULL,
    owner_name   VARCHAR(32) DEFAULT NULL,
    purchased_at DATETIME DEFAULT NULL,
    INDEX idx_parcel_pos (x, y),
    FOREIGN KEY (town_id)  REFERENCES towns(id),
    FOREIGN KEY (owner_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS structures (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    parcel_id      INT NOT NULL,
    x              INT NOT NULL,
    y              INT NOT NULL,
    structure_type VARCHAR(32) NOT NULL,
    level          INT DEFAULT 1,
    inventory      JSON DEFAULT '{}',
    config         JSON DEFAULT '{}',
    last_tick      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parcel_id) REFERENCES world_parcels(id)
);

CREATE TABLE IF NOT EXISTS resource_piles (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    parcel_id     INT DEFAULT NULL,
    owner_id      INT NOT NULL,
    x             INT NOT NULL,
    y             INT NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    amount        FLOAT NOT NULL DEFAULT 0,
    sell_price    FLOAT DEFAULT NULL,
    UNIQUE KEY idx_pile (x, y, resource_type),
    FOREIGN KEY (owner_id)  REFERENCES players(id)
);

-- Dirt road tiles (NPC districts + growth toward player structures)
CREATE TABLE IF NOT EXISTS world_roads (
    x INT NOT NULL,
    y INT NOT NULL,
    protected TINYINT NOT NULL DEFAULT 0,
    PRIMARY KEY (x, y)
);

-- Water (ponds / streams). Movement blocked unless a bridge covers the tile.
CREATE TABLE IF NOT EXISTS water_tiles (
    x INT NOT NULL,
    y INT NOT NULL,
    PRIMARY KEY (x, y)
);

-- Completed wooden bridges (walkable; tile no longer counts as water)
CREATE TABLE IF NOT EXISTS bridge_tiles (
    x INT NOT NULL,
    y INT NOT NULL,
    PRIMARY KEY (x, y)
);

-- In-progress bridge: pay coins once, then deposit wood until BRIDGE_WOOD_REQUIRED
CREATE TABLE IF NOT EXISTS bridge_progress (
    x INT NOT NULL,
    y INT NOT NULL,
    wood_deposited FLOAT NOT NULL DEFAULT 0,
    coins_paid TINYINT NOT NULL DEFAULT 0,
    PRIMARY KEY (x, y)
);

-- Farmland tiles that need 1 dirt delivered before tilling works
CREATE TABLE IF NOT EXISTS poor_soil_tiles (
    x INT NOT NULL,
    y INT NOT NULL,
    PRIMARY KEY (x, y)
);

CREATE TABLE IF NOT EXISTS crops (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    parcel_id     INT NOT NULL,
    owner_id      INT NOT NULL,
    x             INT NOT NULL,
    y             INT NOT NULL,
    crop_type     VARCHAR(32) NOT NULL DEFAULT 'wheat',
    planted_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fertilized_at DATETIME DEFAULT NULL,
    ready_at      DATETIME NOT NULL,
    harvested     TINYINT DEFAULT 0,
    winter_dead   TINYINT NOT NULL DEFAULT 0,
    UNIQUE KEY idx_crop_xy (x, y),
    FOREIGN KEY (parcel_id) REFERENCES world_parcels(id),
    FOREIGN KEY (owner_id)  REFERENCES players(id)
);

-- Farm tile: tilled=1 means soil is ready for seeds; 0 or missing = must till first
CREATE TABLE IF NOT EXISTS soil_tiles (
    x       INT NOT NULL,
    y       INT NOT NULL,
    tilled  TINYINT NOT NULL DEFAULT 0,
    PRIMARY KEY (x, y)
);

CREATE TABLE IF NOT EXISTS season_state (
    id           INT DEFAULT 1 PRIMARY KEY,
    season       TINYINT NOT NULL DEFAULT 0,
    season_start DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_prices (
    resource_type  VARCHAR(32) PRIMARY KEY,
    price_per_unit FLOAT NOT NULL,
    last_updated   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Town elections
CREATE TABLE IF NOT EXISTS town_votes (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    town_id      INT NOT NULL,
    voter_id     INT NOT NULL,
    candidate_id INT NOT NULL,
    vote_cycle   INT NOT NULL DEFAULT 1,
    voted_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_vote (town_id, voter_id, vote_cycle),
    FOREIGN KEY (town_id)      REFERENCES towns(id),
    FOREIGN KEY (voter_id)     REFERENCES players(id),
    FOREIGN KEY (candidate_id) REFERENCES players(id)
);

-- Town leader powers: banned structures / goods within town
CREATE TABLE IF NOT EXISTS town_bans (
    town_id  INT NOT NULL,
    ban_type ENUM('structure','good') NOT NULL,
    target   VARCHAR(32) NOT NULL,
    PRIMARY KEY (town_id, ban_type, target),
    FOREIGN KEY (town_id) REFERENCES towns(id)
);

-- World generation flag: prevents re-generating on every restart
CREATE TABLE IF NOT EXISTS world_gen_state (
    id   INT DEFAULT 1 PRIMARY KEY,
    done TINYINT DEFAULT 0
);
INSERT INTO world_gen_state (id, done) VALUES (1, 0) ON DUPLICATE KEY UPDATE id=id;

-- Season start
INSERT INTO season_state (id, season, season_start) VALUES (1, 0, NOW())
    ON DUPLICATE KEY UPDATE id=id;

-- NPC market prices
INSERT INTO market_prices (resource_type, price_per_unit) VALUES
('manure',  5.0), ('gravel',  3.0), ('topsoil', 3.0), ('compost', 4.0),
('wood',    3.0), ('stone',   4.0), ('clay',    2.5), ('dirt',    1.0),
('wheat',   5.0), ('fertilizer', 12.0)
ON DUPLICATE KEY UPDATE price_per_unit = VALUES(price_per_unit);
