"""Tax-ledger table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset(
    {"tax_events", "taxbase_snapshots", "contribution_ledger", "harvest_ledger"}
)
