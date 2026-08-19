"""Static table-ownership contract shared by persistence repositories."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset()


class RepoContract:
    """Marker for CI checks enforcing declared, disjoint, complete write ownership."""


__all__ = ["TABLES", "RepoContract"]
