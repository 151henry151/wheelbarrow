"""
Rolling terrain elevation (mirrors client/js/terrain.js).

Used for documentation and any future server-side movement validation.
"""
from __future__ import annotations

import math


def elevation_raw(tx: int, ty: int) -> float:
    """Smooth ~[-1, 1] height field on integer tile coords."""
    fx = tx * 0.06
    fy = ty * 0.07
    return (
        math.sin(fx + fy * 0.71) * 0.5
        + math.cos(fx * 0.55 - fy * 0.8) * 0.35
        + math.sin((tx + ty) * 0.095) * 0.15
    )


def world_y_units(tx: int, ty: int) -> float:
    """Nominal vertical offset in client world units (matches Terrain.worldY)."""
    return 2.0 + elevation_raw(tx, ty) * 8.0
