WORLD_W = 100          # tiles wide
WORLD_H = 100          # tiles tall
TILE_SIZE = 32         # pixels per tile (client rendering)
PLAYER_SPAWN = (50, 50)

MARKET_TILE = (50, 60)

COLLECTION_RADIUS = 1   # tiles
COLLECTION_RATE   = 2.0 # units per resource tick when adjacent

PARCEL_SIZE  = 10    # tiles per parcel side
LAND_PRICE   = 500   # coins per parcel

# Structure definitions: what you can build on owned land
STRUCTURE_DEFS = {
    "stable": {
        "label":         "Horse Stable",
        "cost_coins":    200,
        "cost_resources": {},
        "produces":      "manure",
        "replenish_rate": 1.0,
        "max_amount":    200,
        "collect_fee":   1,   # coins paid to owner per collection event
    },
    "gravel_pit": {
        "label":         "Gravel Pit",
        "cost_coins":    300,
        "cost_resources": {"gravel": 20},
        "produces":      "gravel",
        "replenish_rate": 0.6,
        "max_amount":    200,
        "collect_fee":   1,
    },
    "compost_heap": {
        "label":         "Compost Heap",
        "cost_coins":    150,
        "cost_resources": {"manure": 10},
        "produces":      "compost",
        "replenish_rate": 0.4,
        "max_amount":    150,
        "collect_fee":   1,
    },
    "topsoil_mound": {
        "label":         "Topsoil Mound",
        "cost_coins":    250,
        "cost_resources": {"topsoil": 20},
        "produces":      "topsoil",
        "replenish_rate": 0.5,
        "max_amount":    150,
        "collect_fee":   1,
    },
}

MARKET_BASE_PRICES = {
    "manure":  2.0,
    "gravel":  3.0,
    "topsoil": 3.0,
    "compost": 4.0,
}

MARKET_DRIFT_INTERVAL = 60   # seconds between price drift ticks
MARKET_DRIFT_THRESHOLD = 50  # units sold before price starts dropping
