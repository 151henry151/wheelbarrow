WORLD_W = 100
WORLD_H = 100
TILE_SIZE = 32
PLAYER_SPAWN = (50, 50)

MARKET_TILE = (50, 60)   # NPC primary market — always here, can't be bought

COLLECTION_RADIUS = 1
COLLECTION_RATE   = 2.0  # units per resource tick when adjacent

PARCEL_SIZE = 10
LAND_PRICE  = 500

# ---- Seasons ----------------------------------------------------------------
SEASON_DURATION_S = 900    # 15 minutes per season (real-world seconds)
SEASON_NAMES      = ["spring", "summer", "fall", "winter"]
# 0=spring (plant crops), 1=summer (fertilize), 2=fall (harvest), 3=winter

# ---- Wheelbarrow condition (per move) --------------------------------------
WB_DECAY_PAINT  = 0.015
WB_DECAY_TIRE   = 0.020
WB_DECAY_HANDLE = 0.012

WB_FLAT_THRESH  = 25    # tire cond below this → random flat chance
WB_BREAK_THRESH = 15    # handle cond below this → random break chance
WB_HOLE_THRESH  = 20    # paint cond below this → random spill chance
WB_SPILL_AMT    = 0.5   # units spilled per move when holed

# Base random probability per move when below threshold
WB_PROB_FLAT  = 0.0030
WB_PROB_BREAK = 0.0015
WB_PROB_HOLE  = 0.0040

# ---- Wheelbarrow upgrades — 6 levels each ----------------------------------
# Level 1 = default stock wheelbarrow.

# Barrow (bucket capacity)
WB_BUCKET_CAP  = {1: 10, 2: 16, 3: 26, 4: 40, 5: 60, 6: 85}
WB_BUCKET_COST = {2: 600, 3: 1800, 4: 5500, 5: 16000, 6: 45000}

# Tires: flat-chance multiplier (lower = better)
WB_TIRE_FLAT_MULT = {1: 1.00, 2: 0.72, 3: 0.50, 4: 0.33, 5: 0.20, 6: 0.11}
WB_TIRE_COST      = {2: 400,  3: 1200, 4: 4000, 5: 12000, 6: 35000}

# Handle: break-chance multiplier
WB_HANDLE_BREAK_MULT = {1: 1.00, 2: 0.70, 3: 0.48, 4: 0.30, 5: 0.18, 6: 0.10}
WB_HANDLE_COST       = {2: 500,  3: 1500, 4: 4500, 5: 13000, 6: 38000}

# Barrow material: paint-decay multiplier (stainless = low)
WB_BARROW_DECAY_MULT = {1: 1.00, 2: 0.75, 3: 0.55, 4: 0.38, 5: 0.22, 6: 0.12}
WB_BARROW_COST       = {2: 700,  3: 2000, 4: 6000, 5: 18000, 6: 50000}

UPGRADE_COMPONENTS = {
    "bucket":  (WB_BUCKET_CAP,  WB_BUCKET_COST,  "Barrow size"),
    "tire":    (WB_TIRE_FLAT_MULT,   WB_TIRE_COST,    "Tire quality"),
    "handle":  (WB_HANDLE_BREAK_MULT, WB_HANDLE_COST, "Handle quality"),
    "barrow":  (WB_BARROW_DECAY_MULT, WB_BARROW_COST, "Barrow material"),
}

# ---- Repair -----------------------------------------------------------------
REPAIR_COST_PER_PCT = {"paint": 0.30, "tire": 0.50, "handle": 0.60}
REPAIR_FLAT_COST    = 40   # coins to fix a flat tire

# ---- NPC shops --------------------------------------------------------------
NPC_SHOP_LOCATIONS = {
    "seed_shop":     (56, 50),
    "general_store": (44, 50),
    "repair_shop":   (50, 44),
}
NPC_SHOP_LABELS = {
    "seed_shop":     "Seed Shop",
    "general_store": "General Store",
    "repair_shop":   "Repair Shop",
}
NPC_SHOP_ADJACENCY = 1   # tiles radius to "be at" an NPC shop

# Seed shop catalog: item_key -> info
SEED_SHOP_ITEMS = {
    "wheat_seed":  {"label": "Wheat Seeds x10", "cost": 25,  "qty": 10},
    "fertilizer":  {"label": "Fertilizer x5",   "cost": 20,  "qty": 5},
}

# ---- Farming ----------------------------------------------------------------
CROP_DEFS = {
    "wheat": {
        "label":              "Wheat",
        "seed_item":          "wheat_seed",
        "grow_time_s":        20 * 60,
        "grow_time_fert_s":   10 * 60,
        "fertilize_window_s": 10 * 60,  # must fertilize within 10 min of planting
        "yield_base":         8,
        "yield_fertilized":   16,
        "plant_season":       0,   # spring
        "harvest_season":     2,   # fall
    }
}

# ---- Structures (player-built on owned land) --------------------------------
STRUCTURE_DEFS = {
    "stable": {
        "label":          "Horse Stable",
        "cost_coins":     200,
        "cost_resources": {},
        "produces":       "manure",
        "replenish_rate": 1.0,
        "max_amount":     200,
        "collect_fee":    1,
    },
    "gravel_pit": {
        "label":          "Gravel Pit",
        "cost_coins":     300,
        "cost_resources": {"gravel": 20},
        "produces":       "gravel",
        "replenish_rate": 0.6,
        "max_amount":     200,
        "collect_fee":    1,
    },
    "compost_heap": {
        "label":          "Compost Heap",
        "cost_coins":     150,
        "cost_resources": {"manure": 10},
        "produces":       "compost",
        "replenish_rate": 0.4,
        "max_amount":     150,
        "collect_fee":    1,
    },
    "topsoil_mound": {
        "label":          "Topsoil Mound",
        "cost_coins":     250,
        "cost_resources": {"topsoil": 20},
        "produces":       "topsoil",
        "replenish_rate": 0.5,
        "max_amount":     150,
        "collect_fee":    1,
    },
    # Player market: allows owner to set buy/sell prices for any goods.
    # Very expensive — the primary economic advantage for serious players.
    "market": {
        "label":          "Player Market",
        "cost_coins":     2000,
        "cost_resources": {"wood": 50, "stone": 30},
        "produces":       None,
        "replenish_rate": 0,
        "max_amount":     0,
        "collect_fee":    0,
        "is_market":      True,
    },
}

# ---- NPC primary market prices (baseline) -----------------------------------
MARKET_BASE_PRICES = {
    "manure":  2.0,
    "gravel":  3.0,
    "topsoil": 3.0,
    "compost": 4.0,
    "wood":    3.0,
    "stone":   4.0,
    "clay":    2.5,
    "dirt":    1.0,
    "wheat":   5.0,
}

MARKET_DRIFT_INTERVAL  = 60   # seconds
MARKET_DRIFT_THRESHOLD = 50   # units sold before price drops
