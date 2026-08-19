"""Append-only experiment table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset({"experiments", "experiment_events"})
