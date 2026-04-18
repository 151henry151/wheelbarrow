"""
Rolling terrain elevation (mirrors client/js/terrain.js).

Used by movement (slope timing) and must stay in sync with the client.
"""
from __future__ import annotations

import math

# Same as client/js/terrain.js WORLD_Y_SCALE — tiles are 32 units; small values read flat.
WORLD_Y_SCALE = 48.0


def elevation_raw(tx: int, ty: int) -> float:
    """Smooth ~[-1, 1] height field on integer tile coords."""
    fx = tx * 0.06
    fy = ty * 0.07
    low = (
        math.sin(fx + fy * 0.71) * 0.5
        + math.cos(fx * 0.55 - fy * 0.8) * 0.35
        + math.sin((tx + ty) * 0.095) * 0.15
    )
    med = math.sin(tx * 0.14 + ty * 0.11) * 0.12 + math.cos(tx * 0.09 - ty * 0.13) * 0.08
    r = low + med
    return max(-1.0, min(1.0, r))


def world_y_units(tx: int, ty: int) -> float:
    """Nominal vertical offset in client world units (matches Terrain.worldY)."""
    return 2.0 + elevation_raw(tx, ty) * WORLD_Y_SCALE
