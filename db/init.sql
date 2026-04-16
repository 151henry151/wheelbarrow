-- Wheelbarrow MMO schema — v0.4.0

CREATE TABLE IF NOT EXISTS players (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    username          VARCHAR(32) UNIQUE NOT NULL,
    password_hash     VARCHAR(128),
    coins             INT DEFAULT 0,
    x                 INT DEFAULT 50,
    y                 INT DEFAULT 50,
    bucket            JSON DEFAULT '{}',
    bucket_cap        INT DEFAULT 10,
    pocket            JSON DEFAULT '{}',
    -- Wheelbarrow condition (0–100)
    wb_paint          FLOAT DEFAULT 100,
    wb_tire           FLOAT DEFAULT 100,
    wb_handle         FLOAT DEFAULT 100,
    flat_tire         TINYINT DEFAULT 0,
    -- Wheelbarrow upgrade levels (1–6)
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
    replenish_rate  FLOAT NOT NULL,   -- units per second; low = depletes fast
    last_tick       DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_position (x, y)
);

CREATE TABLE IF NOT EXISTS land_parcels (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    owner_id     INT NOT NULL,
    x            INT NOT NULL,
    y            INT NOT NULL,
    width        INT DEFAULT 10,
    height       INT DEFAULT 10,
    purchased_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS structures (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    parcel_id      INT NOT NULL,
    x              INT NOT NULL,
    y              INT NOT NULL,
    structure_type VARCHAR(32) NOT NULL,
    level          INT DEFAULT 1,
    -- For player markets: inventory held by the market, and owner-set prices
    inventory      JSON DEFAULT '{}',
    config         JSON DEFAULT '{}',
    last_tick      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parcel_id) REFERENCES land_parcels(id)
);

-- Resource piles: players unload their bucket onto owned land.
-- The owner can optionally set a sell_price; others can then buy.
-- Each (x, y, resource_type) is unique — one pile per type per tile.
CREATE TABLE IF NOT EXISTS resource_piles (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    parcel_id     INT NOT NULL,
    owner_id      INT NOT NULL,
    x             INT NOT NULL,
    y             INT NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    amount        FLOAT NOT NULL DEFAULT 0,
    sell_price    FLOAT DEFAULT NULL,   -- NULL = not for sale to others
    UNIQUE KEY idx_pile (x, y, resource_type),
    FOREIGN KEY (parcel_id) REFERENCES land_parcels(id),
    FOREIGN KEY (owner_id)  REFERENCES players(id)
);

-- Crop plots on owned land
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
    UNIQUE KEY idx_crop_xy (x, y),
    FOREIGN KEY (parcel_id) REFERENCES land_parcels(id),
    FOREIGN KEY (owner_id)  REFERENCES players(id)
);

-- Season persistence: one row, id=1
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

-- ============================================================
-- Seeds
-- ============================================================

-- Starter resource nodes near spawn (high replenish — gateway resources)
INSERT INTO resource_nodes (x, y, node_type, current_amount, max_amount, replenish_rate) VALUES
(44, 46, 'manure',  80, 100, 0.50),
(46, 44, 'manure',  60, 100, 0.50),
(54, 46, 'manure',  70, 100, 0.50),
(56, 44, 'manure',  90, 100, 0.50),
(44, 54, 'gravel',  50, 100, 0.30),
(56, 54, 'gravel',  40, 100, 0.30),
(50, 44, 'topsoil', 60,  80, 0.40),
(50, 56, 'compost', 30,  80, 0.20);

-- Wood (forests in corners — slow replenish, will deplete if over-harvested)
INSERT INTO resource_nodes (x, y, node_type, current_amount, max_amount, replenish_rate) VALUES
( 8,  8, 'wood', 50, 80, 0.04),
(12, 10, 'wood', 40, 80, 0.04),
(10, 14, 'wood', 45, 80, 0.04),
( 6, 15, 'wood', 60, 80, 0.04),
(15,  7, 'wood', 35, 80, 0.04),
(88,  8, 'wood', 55, 80, 0.04),
(85, 12, 'wood', 40, 80, 0.04),
(92, 10, 'wood', 50, 80, 0.04),
(90, 15, 'wood', 45, 80, 0.04),
(87,  7, 'wood', 60, 80, 0.04),
( 8, 88, 'wood', 50, 80, 0.04),
(12, 90, 'wood', 40, 80, 0.04),
(10, 85, 'wood', 55, 80, 0.04),
(88, 88, 'wood', 45, 80, 0.04),
(85, 92, 'wood', 50, 80, 0.04),
(25, 25, 'wood', 35, 60, 0.03),
(75, 25, 'wood', 40, 60, 0.03),
(25, 75, 'wood', 35, 60, 0.03),
(75, 75, 'wood', 40, 60, 0.03);

-- Stone (edges, very slow replenish — scarce, strategically valuable)
INSERT INTO resource_nodes (x, y, node_type, current_amount, max_amount, replenish_rate) VALUES
( 5, 50, 'stone', 80, 120, 0.02),
(95, 50, 'stone', 80, 120, 0.02),
(50,  5, 'stone', 75, 120, 0.02),
(50, 95, 'stone', 70, 120, 0.02),
(20, 35, 'stone', 60,  90, 0.02),
(80, 35, 'stone', 65,  90, 0.02),
(20, 65, 'stone', 55,  90, 0.02),
(80, 65, 'stone', 60,  90, 0.02),
(38, 22, 'stone', 50,  80, 0.02),
(62, 22, 'stone', 55,  80, 0.02),
(38, 78, 'stone', 50,  80, 0.02),
(62, 78, 'stone', 55,  80, 0.02);

-- Clay (middle zones, moderate replenish)
INSERT INTO resource_nodes (x, y, node_type, current_amount, max_amount, replenish_rate) VALUES
(22, 50, 'clay', 60, 100, 0.05),
(78, 50, 'clay', 55, 100, 0.05),
(50, 22, 'clay', 50, 100, 0.05),
(50, 78, 'clay', 60, 100, 0.05),
(33, 60, 'clay', 45,  80, 0.04),
(67, 40, 'clay', 50,  80, 0.04),
(35, 42, 'clay', 40,  80, 0.04),
(65, 58, 'clay', 45,  80, 0.04);

-- Dirt (widespread, faster replenish but only worth 1c/unit)
INSERT INTO resource_nodes (x, y, node_type, current_amount, max_amount, replenish_rate) VALUES
(15, 30, 'dirt', 40, 60, 0.07),
(85, 30, 'dirt', 35, 60, 0.07),
(15, 70, 'dirt', 40, 60, 0.07),
(85, 70, 'dirt', 38, 60, 0.07),
(30, 15, 'dirt', 45, 60, 0.07),
(70, 15, 'dirt', 40, 60, 0.07),
(30, 85, 'dirt', 42, 60, 0.07),
(70, 85, 'dirt', 38, 60, 0.07),
(40, 48, 'dirt', 30, 50, 0.06),
(60, 52, 'dirt', 35, 50, 0.06),
(48, 40, 'dirt', 32, 50, 0.06),
(52, 60, 'dirt', 30, 50, 0.06);

-- Starting season (spring)
INSERT INTO season_state (id, season, season_start) VALUES (1, 0, NOW());

-- NPC market prices (baseline — drift adjusts these)
INSERT INTO market_prices (resource_type, price_per_unit) VALUES
('manure',  2.0),
('gravel',  3.0),
('topsoil', 3.0),
('compost', 4.0),
('wood',    3.0),
('stone',   4.0),
('clay',    2.5),
('dirt',    1.0),
('wheat',   5.0);
