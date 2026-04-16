-- Wheelbarrow MMO schema

CREATE TABLE IF NOT EXISTS players (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(32) UNIQUE NOT NULL,
    password_hash VARCHAR(128),
    coins         INT DEFAULT 0,
    x             INT DEFAULT 50,
    y             INT DEFAULT 50,
    bucket        JSON DEFAULT '{}',
    bucket_cap    INT DEFAULT 10,
    last_seen     DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_nodes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    x               INT NOT NULL,
    y               INT NOT NULL,
    node_type       VARCHAR(32) NOT NULL,
    current_amount  FLOAT DEFAULT 0,
    max_amount      FLOAT NOT NULL,
    replenish_rate  FLOAT NOT NULL,   -- units per second
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
    last_tick      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parcel_id) REFERENCES land_parcels(id)
);

CREATE TABLE IF NOT EXISTS market_prices (
    resource_type  VARCHAR(32) PRIMARY KEY,
    price_per_unit FLOAT NOT NULL,
    last_updated   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed: free resource nodes in the starting zone so new players can bootstrap
INSERT INTO resource_nodes (x, y, node_type, current_amount, max_amount, replenish_rate) VALUES
(44, 46, 'manure',  80, 100, 0.5),
(46, 44, 'manure',  60, 100, 0.5),
(54, 46, 'manure',  70, 100, 0.5),
(56, 44, 'manure',  90, 100, 0.5),
(44, 54, 'gravel',  50, 100, 0.3),
(56, 54, 'gravel',  40, 100, 0.3),
(50, 44, 'topsoil', 60,  80, 0.4),
(50, 56, 'compost', 30,  80, 0.2);

-- Seed: starting market prices
INSERT INTO market_prices (resource_type, price_per_unit) VALUES
('manure',  2),
('gravel',  3),
('topsoil', 3),
('compost', 4);
