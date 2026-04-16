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
    """Chain consecutive sites with BFS paths inside polygon; union all path tiles."""
    sites_l = list(sites)
    if len(sites_l) < 2:
        return set(sites_l)

    def passable(tx: int, ty: int) -> bool:
        if (tx, ty) in extra_blocked:
            return False
        return _point_in_polygon(tx + 0.5, ty + 0.5, poly)

    roads: set[tuple[int, int]] = set()
    # Always mark each business tile as road so shops sit on dirt even if path skirts the tile
    roads.update(sites_l)
    for i in range(len(sites_l) - 1):
        p = bfs_path_4(sites_l[i], sites_l[i + 1], passable)
        if p:
            roads.update(p)
    p = bfs_path_4(sites_l[-1], sites_l[0], passable)
    if p:
        roads.update(p)
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
