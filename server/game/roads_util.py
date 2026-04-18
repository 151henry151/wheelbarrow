"""
Road tile pathfinding (4-neighbour BFS) and helpers for initial NPC districts + growth.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Iterable

from server.game.town_npcs import _point_in_polygon


def bfs_path_4(
    start: tuple[int, int],
    goal: tuple[int, int],
    passable: Callable[[int, int], bool],
    max_iter: int = 80000,
) -> list[tuple[int, int]] | None:
    """Shortest 4-neighbour path start→goal; tiles must satisfy passable(tx,ty)."""
    if start == goal:
        return [start]
    if not passable(*start) or not passable(*goal):
        return None
    q = deque([start])
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    steps = 0
    while q and steps < max_iter:
        steps += 1
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in came:
                continue
            if not passable(nx, ny):
                continue
            came[(nx, ny)] = (x, y)
            if (nx, ny) == goal:
                out = [(nx, ny)]
                cur = (x, y)
                while cur is not None:
                    out.append(cur)
                    cur = came[cur]
                out.reverse()
                return out
            q.append((nx, ny))
    return None


def path_union_for_sites(
    poly: list[dict],
    sites: Iterable[tuple[int, int]],
    extra_blocked: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """
    Connect all NPC district sites with BFS paths inside the town polygon (4-neighbour).

    Uses a Prim-style build: repeatedly connect one not-yet-linked site to the growing
    component using the shortest available BFS path. A fixed ring (market→…→repair→market)
    often missed edges when a segment failed or was long; this keeps every reachable site
    on one dirt network.
    """
    sites_l = list(dict.fromkeys(sites))
    if len(sites_l) < 2:
        return set(sites_l)

    def passable(tx: int, ty: int) -> bool:
        if (tx, ty) in extra_blocked:
            return False
        return _point_in_polygon(tx + 0.5, ty + 0.5, poly)

    roads: set[tuple[int, int]] = set(sites_l)
    connected = {sites_l[0]}
    unconnected = set(sites_l[1:])

    while unconnected:
        best_path: list[tuple[int, int]] | None = None
        best_g: tuple[int, int] | None = None
        best_len = 10**9
        for g in unconnected:
            for c in connected:
                p = bfs_path_4(c, g, passable)
                if p and len(p) < best_len:
                    best_len = len(p)
                    best_path = p
                    best_g = g
        if best_path is None or best_g is None:
            break
        roads.update(best_path)
        connected.add(best_g)
        unconnected.remove(best_g)

    return roads


def nearest_tile_in_set(goal: tuple[int, int], tiles: set[tuple[int, int]]) -> tuple[int, int] | None:
    if not tiles:
        return None
    return min(tiles, key=lambda t: abs(t[0] - goal[0]) + abs(t[1] - goal[1]))


def pick_adjacent_growth_tile(
    road_tiles: set[tuple[int, int]],
    goal: tuple[int, int],
    blocked: set[tuple[int, int]],
    world_w: int,
    world_h: int,
) -> tuple[int, int] | None:
    """
    Pick a passable non-road tile that is 4-adjacent to some road tile and
    minimizes Manhattan distance to goal (road grows one step toward the building).
    """
    best: tuple[int, int] | None = None
    best_d = 10**9
    for rx, ry in road_tiles:
        for nx, ny in ((rx + 1, ry), (rx - 1, ry), (rx, ry + 1), (rx, ry - 1)):
            if nx < 0 or ny < 0 or nx >= world_w or ny >= world_h:
                continue
            if (nx, ny) in road_tiles or (nx, ny) in blocked:
                continue
            d = abs(nx - goal[0]) + abs(ny - goal[1])
            if d < best_d:
                best_d = d
                best = (nx, ny)
    return best
