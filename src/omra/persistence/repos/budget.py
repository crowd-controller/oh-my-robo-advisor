"""Canary and change-budget table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset({"canary_state", "change_budget"})
