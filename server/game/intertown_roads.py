"""
Inter-town dirt road network + bridges at river crossings (world generation only).

Roads are inserted with protected=1 so gameplay rules can forbid altering them.
"""
from __future__ import annotations

import heapq
import math
import random
from collections import deque
from typing import Callable

from server.game.constants import WORLD_H, WORLD_W


def _bfs_path_4(
    start: tuple[int, int],
    goal: tuple[int, int],
    passable: Callable[[int, int], bool],
    max_iter: int = 200_000,
) -> list[tuple[int, int]] | None:
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


def _a_star_water_allowed(
    start: tuple[int, int],
    goal: tuple[int, int],
    water: set[tuple[int, int]],
) -> list[tuple[int, int]] | None:
    """Path from start to goal; land preferred; water tiles allowed (bridged later)."""
    if start == goal:
        return [start]

    def h(a: tuple[int, int]) -> float:
        return abs(a[0] - goal[0]) + abs(a[1] - goal[1])

    def pass_land(tx: int, ty: int) -> bool:
        if tx < 0 or ty < 0 or tx >= WORLD_W or ty >= WORLD_H:
            return False
        return (tx, ty) not in water

    def pass_any(tx: int, ty: int) -> bool:
        return 0 <= tx < WORLD_W and 0 <= ty < WORLD_H

    p0 = _bfs_path_4(start, goal, pass_land)
    if p0:
        return p0

    open_h: list[tuple[float, float, tuple[int, int]]] = []
    heapq.heappush(open_h, (h(start), 0.0, start))
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    visited = 0
    while open_h and visited < 500_000:
        _, gc, cur = heapq.heappop(open_h)
        if cur == goal:
            out = [cur]
            bk = came[cur]
            while bk is not None:
                out.append(bk)
                bk = came[bk]
            out.reverse()
            return out
        cx, cy = cur
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if not pass_any(nx, ny):
                continue
            wcost = 3.0 if (nx, ny) in water else 1.0
            ng = gc + wcost
            if ng < g_score.get((nx, ny), 1e18):
                g_score[(nx, ny)] = ng
                came[(nx, ny)] = cur
                heapq.heappush(open_h, (ng + h((nx, ny)), ng, (nx, ny)))
        visited += 1
    return None


def plan_intertown_roads(
    rng: random.Random,
    towns: list[dict],
    water: set[tuple[int, int]],
) -> tuple[set[tuple[int, int]], set[tuple[int, int]], set[tuple[int, int]]]:
    """
    Returns (road_tiles, bridge_tiles, water_to_remove) for DB application.
    Builds a connected graph on towns, then adds redundancy so most towns have degree >= 2.
    """
    n = len(towns)
    if n < 2:
        return set(), set(), set()

    centers: list[tuple[int, int]] = []
    for t in towns:
        centers.append((int(t["center_x"]), int(t["center_y"])))

    edges_all: list[tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            ax, ay = centers[i]
            bx, by = centers[j]
            d = math.hypot(ax - bx, ay - by)
            edges_all.append((d, i, j))
    edges_all.sort(key=lambda x: x[0])

    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    mst: list[tuple[int, int]] = []
    for _d, i, j in edges_all:
        if union(i, j):
            mst.append((i, j))
        if len(mst) == n - 1:
            break

    deg = [0] * n
    for i, j in mst:
        deg[i] += 1
        deg[j] += 1

    extra: list[tuple[int, int]] = []
    used = {(min(i, j), max(i, j)) for i, j in mst}

    for _pass in range(8):
        need = [i for i in range(n) if deg[i] < 2]
        if not need:
            break
        for i in rng.sample(need, k=len(need)):
            if deg[i] >= 2:
                continue
            best_j = -1
            best_d = 1e18
            for j in range(n):
                if i == j:
                    continue
                k = (min(i, j), max(i, j))
                if k in used:
                    continue
                ax, ay = centers[i]
                bx, by = centers[j]
                d = math.hypot(ax - bx, ay - by)
                if d < best_d:
                    best_d = d
                    best_j = j
            if best_j >= 0:
                k = (min(i, best_j), max(i, best_j))
                used.add(k)
                extra.append((i, best_j))
                deg[i] += 1
                deg[best_j] += 1

    all_edges = mst + extra
    road_tiles: set[tuple[int, int]] = set()
    bridge_tiles: set[tuple[int, int]] = set()
    water_remove: set[tuple[int, int]] = set()
    water_work = set(water)

    for i, j in all_edges:
        ax, ay = centers[i]
        bx, by = centers[j]
        start = (max(0, min(WORLD_W - 1, ax)), max(0, min(WORLD_H - 1, ay)))
        goal = (max(0, min(WORLD_W - 1, bx)), max(0, min(WORLD_H - 1, by)))
        path = _a_star_water_allowed(start, goal, water_work)
        if not path:
            continue
        for tx, ty in path:
            road_tiles.add((tx, ty))
            if (tx, ty) in water_work:
                bridge_tiles.add((tx, ty))
                water_remove.add((tx, ty))
                water_work.discard((tx, ty))

    return road_tiles, bridge_tiles, water_remove
