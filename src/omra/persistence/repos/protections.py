"""Protection state and counter table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset({"protection_state", "protection_counters"})
