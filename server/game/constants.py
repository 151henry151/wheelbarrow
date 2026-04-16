WORLD_W = 1000
WORLD_H = 1000
TILE_SIZE = 32
PLAYER_SPAWN = (500, 500)

# NPC primary market — ~60 tiles south of spawn; not visible at spawn
MARKET_TILE = (500, 560)

COLLECTION_RADIUS = 1
COLLECTION_RATE   = 2.0   # default fallback

# How many units per collection tick each resource type loads into the bucket.
# Light/loose materials load faster; dense/sticky/heavy materials load slower.
# Pile pickup into barrow is slightly faster than harvesting from wild nodes (multiplier > 1)
PILE_COLLECTION_MULT = 1.18

COLLECTION_RATES = {
    "dirt":    3.5,   # loose, dry — loads very quickly
    "wheat":   3.0,   # light stalks
    "gravel":  2.5,   # loose pebbles
    "topsoil": 2.5,   # fine and crumbly
    "manure":  2.5,   # semi-liquid, shovels easily
    "fertilizer": 2.5,
    "wood":    2.0,   # standard — hefty but manageable
    "compost": 1.8,   # chunky organic matter
    "clay":    1.0,   # sticky, dense — loads slowly
    "stone":   0.7,   # heavy chunks — very slow to load
}

# ---- Seasons ----------------------------------------------------------------
SEASON_DURATION_S = 900
SEASON_NAMES      = ["spring", "summer", "fall", "winter"]

# Dirt road growth toward player buildings (~tiles added per in-game year at spring)
ROAD_GROWTH_TILES_MIN = 3
ROAD_GROWTH_TILES_MAX = 7

# ---- Wheelbarrow condition --------------------------------------------------
WB_DECAY_PAINT  = 0.015
WB_DECAY_TIRE   = 0.020
WB_DECAY_HANDLE = 0.012
WB_DECAY_BARROW = 0.005   # only ticks when paint < WB_PAINT_RUST_THRESH

WB_FLAT_THRESH        = 25
WB_BREAK_THRESH       = 15
WB_PAINT_RUST_THRESH  = 50   # paint below this → barrow starts to rust
WB_BARROW_HOLE_THRESH = 60   # barrow below this → cargo starts spilling
WB_SPILL_AMT          = 0.5

WB_PROB_FLAT  = 0.0030
WB_PROB_BREAK = 0.0015
WB_PROB_HOLE  = 0.0400   # per-move spill chance base (at WB_BARROW_HOLE_THRESH)

# ---- Wheelbarrow material / type names --------------------------------------
WB_BARROW_MATERIAL_NAMES = {1: "plastic", 2: "steel",    3: "aluminium"}
WB_TIRE_TYPE_NAMES        = {1: "regular", 2: "tubeless", 3: "heavy-duty"}
WB_HANDLE_MATERIAL_NAMES  = {1: "wood",    2: "steel",    3: "fiberglass"}

# Chassis weights added to movement-speed calculation (client uses these).
# Positive = heavier = slower; negative = lighter = faster.
# Steel barrow and steel handle are heavier; aluminium/fiberglass are lighter.
WB_BARROW_CHASSIS_WEIGHT = {1:  0.0, 2:  5.0, 3: -2.0}  # plastic / steel / aluminium
WB_HANDLE_CHASSIS_WEIGHT = {1:  0.0, 2:  1.5, 3: -0.5}  # wood    / steel / fiberglass

# ---- Wheelbarrow upgrades ---------------------------------------------------
# Bucket size: 6 tiers (capacity upgrade, not tied to a material type)
WB_BUCKET_CAP  = {1: 10, 2: 16, 3: 26, 4: 40, 5: 60, 6: 85}
WB_BUCKET_COST = {2: 600, 3: 1800, 4: 5500, 5: 16000, 6: 45000}

# Tires: 3 named types — regular → tubeless → heavy-duty
# Lower mult = lower flat-tyre probability per move
WB_TIRE_FLAT_MULT = {1: 1.00, 2: 0.50, 3: 0.11}
WB_TIRE_COST      = {2: 400,  3: 4000}

# Handles: 3 named materials — wood → steel → fiberglass
# Lower mult = lower handle-break probability per move
WB_HANDLE_BREAK_MULT = {1: 1.00, 2: 0.48, 3: 0.10}
WB_HANDLE_COST       = {2: 500,  3: 4500}

# Barrow material: 3 named types — plastic → steel → aluminium
# Lower mult = slower overall decay (paint, barrow health)
# Rust behaviour differs per material (see wb_condition.py)
WB_BARROW_DECAY_MULT = {1: 1.00, 2: 0.55, 3: 0.12}
WB_BARROW_COST       = {2: 700,  3: 6000}

UPGRADE_COMPONENTS = {
    "bucket": (WB_BUCKET_CAP,        WB_BUCKET_COST,  "Barrow capacity"),
    "tire":   (WB_TIRE_FLAT_MULT,    WB_TIRE_COST,    "Tire type"),
    "handle": (WB_HANDLE_BREAK_MULT, WB_HANDLE_COST,  "Handle material"),
    "barrow": (WB_BARROW_DECAY_MULT, WB_BARROW_COST,  "Barrow material"),
}

# ---- Resource weights (heavier = slower movement when loaded) ---------------
RESOURCE_WEIGHTS = {
    "wood":    0.5,
    "wheat":   0.6,
    "fertilizer": 0.65,
    "compost": 0.7,
    "manure":  0.8,
    "topsoil": 1.2,
    "dirt":    1.5,
    "clay":    1.8,
    "stone":   2.0,
    "gravel":  2.5,
}
RESOURCE_WEIGHT_DEFAULT = 1.0

# ---- Repair -----------------------------------------------------------------
REPAIR_COST_PER_PCT = {"paint": 3.0, "tire": 5.0, "handle": 6.0, "barrow": 4.5}
REPAIR_FLAT_COST    = 40

# ---- NPC shops --------------------------------------------------------------
# NPC shops: 50-60 tiles from spawn in different directions — not visible at start
NPC_SHOP_LOCATIONS = {
    "seed_shop":     (556, 500),   # ~56 tiles east
    "general_store": (444, 500),   # ~56 tiles west
    "repair_shop":   (500, 444),   # ~56 tiles north
}
NPC_SHOP_LABELS = {
    "seed_shop":     "Seed Shop",
    "general_store": "General Store",
    "repair_shop":   "Repair Shop",
}
NPC_SHOP_ADJACENCY = 1

SEED_SHOP_ITEMS = {
    "wheat_seed": {"label": "Wheat Seeds ×10", "cost": 25, "qty": 10},
    # ~2× manure NPC buy price per unit (manure 5c → 10c/unit → 5 units = 50c)
    "fertilizer": {"label": "Fertilizer ×5",   "cost": 50, "qty": 5},
}

# ---- Farming ----------------------------------------------------------------
CROP_DEFS = {
    "wheat": {
        "label":              "Wheat",
        "seed_item":          "wheat_seed",
        "grow_time_s":        20 * 60,
        "grow_time_fert_s":   10 * 60,
        "fertilize_window_s": 10 * 60,
        "yield_base":         8,
        "yield_fertilized":   16,
        "plant_season":       0,
        "harvest_season":     2,
    }
}

# ---- Structures -------------------------------------------------------------
# Pay init_coins to place the construction site, then deposit foundation materials, then building.
STRUCTURE_DEFS = {
    "stable": {
        "label": "Horse Stable",
        "construction": {
            "init_coins": 200,
            "foundation": {"stone": 30},
            "building": {"wood": 40},
        },
        "produces": "manure", "replenish_rate": 1.0, "max_amount": 200, "collect_fee": 1,
    },
    "gravel_pit": {
        "label": "Gravel Pit",
        "construction": {
            "init_coins": 300,
            "foundation": {"stone": 40},
            "building": {"gravel": 20, "wood": 15},
        },
        "produces": "gravel", "replenish_rate": 0.6, "max_amount": 200, "collect_fee": 1,
    },
    "compost_heap": {
        "label": "Compost Heap",
        "construction": {
            "init_coins": 150,
            "foundation": {"stone": 20},
            "building": {"manure": 10, "wood": 20},
        },
        "produces": "compost", "replenish_rate": 0.4, "max_amount": 150, "collect_fee": 1,
    },
    "topsoil_mound": {
        "label": "Topsoil Mound",
        "construction": {
            "init_coins": 250,
            "foundation": {"stone": 25},
            "building": {"topsoil": 20, "wood": 25},
        },
        "produces": "topsoil", "replenish_rate": 0.5, "max_amount": 150, "collect_fee": 1,
    },
    "market": {
        "label": "Player Market",
        "construction": {
            "init_coins": 2000,
            "foundation": {"stone": 30},
            "building": {"wood": 50},
        },
        "produces": None, "replenish_rate": 0, "max_amount": 0, "collect_fee": 0,
        "is_market": True,
    },
    "town_hall": {
        "label": "Town Hall",
        "construction": {
            "init_coins": 5000,
            "foundation": {"stone": 50, "gravel": 20},
            "building": {"wood": 50, "dirt": 100},
        },
        "produces": None, "replenish_rate": 0, "max_amount": 0, "collect_fee": 0,
        "is_town_hall": True,
    },
    "silo": {
        "label": "Grain Silo",
        "construction": {
            "init_coins": 500,
            "foundation": {"stone": 60},
            "building": {"wood": 80},
        },
        "produces": None, "replenish_rate": 0, "max_amount": 0, "collect_fee": 0,
        "is_silo": True,
        "silo_capacity": 5000.0,
    },
}

# Pile contents that rot in winter (converted to compost on the same tile)
WINTER_PILE_SPOIL_TYPES = frozenset({"wheat"})

# ---- Towns ------------------------------------------------------------------
TOWN_ADJ  = ["Old", "New", "Green", "Stone", "River", "Hill", "Dark", "Iron",
             "Golden", "Silver", "Muddy", "Windy", "Quiet", "Merry", "Grim",
             "Bright", "Cold", "Warm", "Lucky", "Lost", "Hollow", "High",
             "Low", "Far", "Near"]
TOWN_NOUN = ["ford", "haven", "dale", "wood", "burg", "ton", "field", "wick",
             "bridge", "hollow", "crossing", "meadow", "ridge", "creek", "vale",
             "gate", "mill", "port", "rise", "bottom", "chapel", "barrow"]

TOWN_COUNT           = 40
TOWN_MIN_DIST        = 160   # minimum tiles between town centres
TOWN_RADIUS_MIN      = 80    # large towns — takes time to cross
TOWN_RADIUS_MAX      = 150
ELECTION_CYCLE_DAYS  = 10    # real-time days between elections
VOTING_WINDOW_HOURS  = 24    # election window length
MAX_TAX_RATE         = 0.30  # 30% sales tax cap

# ---- Parcels ----------------------------------------------------------------
# Price per tile (base), and bonus per resource node within the parcel
PARCEL_PRICE_PER_TILE = 8
PARCEL_RESOURCE_BONUS = 150  # per node inside or adjacent

# Size ranges
PARCEL_W_RANGE = (5, 20)
PARCEL_H_RANGE = (5, 15)
PARCEL_MIN_PRICE = 100

TOWN_PARCELS_PER_TOWN = (8, 20)    # random range
WILDERNESS_PARCELS    = 200        # parcels outside any town

# ---- World viewport -------------------------
# Nodes/piles/crops sent per tick only within this radius of the player
VIEWPORT_RADIUS = 120

# ---- Market -----------------------------------------------------------------
MARKET_BASE_PRICES = {
    "manure": 5.0, "gravel": 3.0, "topsoil": 3.0, "compost": 4.0,
    "wood":   3.0, "stone":  4.0, "clay":   2.5,  "dirt":    1.0,
    "wheat":  5.0, "fertilizer": 12.0,
}
MARKET_DRIFT_INTERVAL  = 60
MARKET_DRIFT_THRESHOLD = 50
