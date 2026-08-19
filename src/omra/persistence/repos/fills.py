"""Matched and unmatched fill table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset({"fills", "unmatched_fills"})
