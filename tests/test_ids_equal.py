"""Engine id comparison used for structure ownership (silo withdraw, etc.)."""
from __future__ import annotations

from server.game.ids import ids_equal


def test_ids_equal_numeric() -> None:
    assert ids_equal(1, 1)
    assert not ids_equal(1, 2)


def test_ids_equal_str_coercion() -> None:
    assert ids_equal("42", 42)
    assert ids_equal(42, "42")


def test_ids_equal_none() -> None:
    assert not ids_equal(None, 1)
    assert not ids_equal(1, None)
