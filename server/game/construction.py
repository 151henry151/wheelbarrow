"""
Multi-phase building: pay init_coins to place a site, then deposit foundation materials,
then building materials, then the structure becomes active.
"""
from __future__ import annotations

from typing import Any


def init_construction_state(sdef: dict) -> dict:
    c = sdef["construction"]
    fd = {k: float(v) for k, v in c.get("foundation", {}).items() if float(v) > 0}
    bd = {k: float(v) for k, v in c.get("building", {}).items() if float(v) > 0}
    return {
        "foundation": fd,
        "building": bd,
        "deposited": {},
        "foundation_done": len(fd) == 0,
    }


def _rem(req: dict[str, float], dep: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, need in req.items():
        have = dep.get(k, 0.0)
        out[k] = max(0.0, float(need) - float(have))
    return out


def foundation_remaining(cons: dict[str, Any]) -> dict[str, float]:
    return _rem(cons.get("foundation", {}), cons.get("deposited", {}))


def building_remaining(cons: dict[str, Any]) -> dict[str, float]:
    return _rem(cons.get("building", {}), cons.get("deposited", {}))


def _apply_take(bucket: dict, cons: dict, rtype: str, take: float) -> None:
    bucket[rtype] = round(bucket[rtype] - take, 2)
    if bucket[rtype] <= 0:
        del bucket[rtype]
    dep = cons.setdefault("deposited", {})
    dep[rtype] = round(dep.get(rtype, 0) + take, 2)


def deposit_all_from_bucket(cons: dict[str, Any], bucket: dict) -> tuple[float, list[str]]:
    """
    Move materials from bucket into construction progress (foundation first, then building).
    Returns (total_units_moved, status_tags e.g. foundation_complete, building_complete).
    """
    tags: list[str] = []
    total = 0.0

    while True:
        fr = foundation_remaining(cons)
        if not any(v > 0 for v in fr.values()):
            cons["foundation_done"] = True
            break
        moved = False
        for rtype in list(bucket.keys()):
            need = fr.get(rtype, 0)
            if need <= 0:
                continue
            take = min(bucket[rtype], need)
            if take <= 0:
                continue
            _apply_take(bucket, cons, rtype, take)
            total += take
            moved = True
            fr = foundation_remaining(cons)
            if not any(v > 0 for v in fr.values()):
                cons["foundation_done"] = True
                tags.append("foundation_complete")
            break
        if not moved:
            break

    while True:
        if not cons.get("foundation_done"):
            break
        br = building_remaining(cons)
        if not any(v > 0 for v in br.values()):
            break
        moved = False
        for rtype in list(bucket.keys()):
            need = br.get(rtype, 0)
            if need <= 0:
                continue
            take = min(bucket[rtype], need)
            if take <= 0:
                continue
            _apply_take(bucket, cons, rtype, take)
            total += take
            moved = True
            br = building_remaining(cons)
            if not any(v > 0 for v in br.values()):
                tags.append("building_complete")
            break
        if not moved:
            break

    return total, tags


def construction_is_complete(cons: dict[str, Any]) -> bool:
    if not cons.get("foundation_done") and any(v > 0 for v in foundation_remaining(cons).values()):
        return False
    return not any(v > 0 for v in building_remaining(cons).values())
