"""Road path union (NPC districts)."""
from server.game.roads_util import path_union_for_sites


def _square_poly(x0: int, y0: int, w: int, h: int) -> list[dict]:
    return [
        {"x": x0, "y": y0},
        {"x": x0 + w, "y": y0},
        {"x": x0 + w, "y": y0 + h},
        {"x": x0, "y": y0 + h},
    ]


def test_path_union_for_sites_connects_all_four_corners():
    poly = _square_poly(100, 100, 20, 20)
    sites = [(105, 105), (115, 105), (115, 115), (105, 115)]
    roads = path_union_for_sites(poly, sites, set())
    for s in sites:
        assert s in roads
    assert len(roads) >= len(sites)


def test_path_union_for_sites_single_site():
    poly = _square_poly(0, 0, 5, 5)
    roads = path_union_for_sites(poly, [(2, 2)], set())
    assert roads == {(2, 2)}
