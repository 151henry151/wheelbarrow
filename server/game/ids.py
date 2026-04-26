"""Numeric id equality (DB / JSON may surface owner_id as str or int)."""


def ids_equal(a, b) -> bool:
    """Return True if ``a`` and ``b`` denote the same integer id."""
    if a is None or b is None:
        return False
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return False
