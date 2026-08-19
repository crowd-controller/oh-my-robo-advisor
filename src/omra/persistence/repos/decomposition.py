"""Portfolio-decomposition table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset(
    {"portfolio_decomposition", "portfolio_decomposition_meta"}
)
