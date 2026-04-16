"""
Wheelbarrow condition degradation and effects.
Called on every player move.
"""
import random
from server.game.constants import (
    WB_DECAY_PAINT, WB_DECAY_TIRE, WB_DECAY_HANDLE, WB_DECAY_BARROW,
    WB_FLAT_THRESH, WB_BREAK_THRESH,
    WB_PAINT_RUST_THRESH, WB_BARROW_HOLE_THRESH, WB_SPILL_AMT,
    WB_PROB_FLAT, WB_PROB_BREAK, WB_PROB_HOLE,
    WB_TIRE_FLAT_MULT, WB_HANDLE_BREAK_MULT, WB_BARROW_DECAY_MULT,
)


def apply_move_decay(player: dict) -> list[str]:
    """
    Degrade WB condition by one move's worth.
    Returns a list of event strings:
        "flat_tire"        — tyre just went flat
        "handle_break"     — handle just broke (wb_handle → 0)
        "spill:<type>:<amt>" — cargo spilled through a hole
    """
    events: list[str] = []

    bl = player.get("wb_barrow_level", 1)
    tl = player.get("wb_tire_level",   1)
    hl = player.get("wb_handle_level", 1)

    barrow_mult = WB_BARROW_DECAY_MULT.get(bl, 1.0)
    tire_mult   = WB_TIRE_FLAT_MULT.get(tl, 1.0)
    handle_mult = WB_HANDLE_BREAK_MULT.get(hl, 1.0)

    # Degrade paint, tire, handle
    player["wb_paint"]  = max(0.0, player.get("wb_paint",  100.0) - WB_DECAY_PAINT  * barrow_mult)
    player["wb_tire"]   = max(0.0, player.get("wb_tire",   100.0) - WB_DECAY_TIRE   * tire_mult)
    player["wb_handle"] = max(0.0, player.get("wb_handle", 100.0) - WB_DECAY_HANDLE * handle_mult)

    # --- Barrow structural wear: depends on material ---
    # steel (2): rusts when paint is low; plastic (1): physical wear always;
    # aluminium (3): barely wears, no paint dependency
    material = player.get("wb_barrow_level", 1)
    if material == 2:   # steel — protected by paint; rusts when paint < threshold
        if player["wb_paint"] < WB_PAINT_RUST_THRESH:
            player["wb_barrow"] = max(0.0, player.get("wb_barrow", 100.0) - WB_DECAY_BARROW * barrow_mult)
    elif material == 1:  # plastic — physical wear, no paint dependency, medium rate
        player["wb_barrow"] = max(0.0, player.get("wb_barrow", 100.0) - WB_DECAY_BARROW * 0.6 * barrow_mult)
    else:               # aluminium — very slow wear, no paint dependency
        player["wb_barrow"] = max(0.0, player.get("wb_barrow", 100.0) - WB_DECAY_BARROW * 0.08 * barrow_mult)

    # --- Flat tyre ---
    if not player.get("flat_tire"):
        tire_cond = player["wb_tire"]
        if tire_cond < WB_FLAT_THRESH:
            ratio = 1.0 - (tire_cond / WB_FLAT_THRESH)
            chance = WB_PROB_FLAT * tire_mult * ratio
            if random.random() < chance:
                player["flat_tire"] = 1
                events.append("flat_tire")

    # --- Handle break ---
    handle_cond = player["wb_handle"]
    if handle_cond < WB_BREAK_THRESH:
        ratio = 1.0 - (handle_cond / WB_BREAK_THRESH)
        chance = WB_PROB_BREAK * handle_mult * ratio
        if random.random() < chance:
            player["wb_handle"] = 0.0
            events.append("handle_break")

    # --- Barrow hole / cargo spill ---
    barrow_cond = player.get("wb_barrow", 100.0)
    if barrow_cond < WB_BARROW_HOLE_THRESH:
        bucket = player.get("bucket", {})
        if bucket:
            ratio = 1.0 - (barrow_cond / WB_BARROW_HOLE_THRESH)
            chance = WB_PROB_HOLE * barrow_mult * ratio
            if random.random() < chance:
                spill_type = random.choice(list(bucket.keys()))
                spill_amt  = min(WB_SPILL_AMT, bucket[spill_type])
                bucket[spill_type] = round(bucket[spill_type] - spill_amt, 2)
                if bucket[spill_type] <= 0:
                    del bucket[spill_type]
                events.append(f"spill:{spill_type}:{round(spill_amt, 2)}")

    return events


def is_immobile(player: dict) -> bool:
    """Returns True when the handle is fully broken and the WB can't move."""
    return player.get("wb_handle", 100.0) <= 0.0


def flat_move_multiplier(player: dict) -> float:
    """Move-interval multiplier. 1.0 = normal speed, >1 = slower."""
    return 3.0 if player.get("flat_tire") else 1.0
