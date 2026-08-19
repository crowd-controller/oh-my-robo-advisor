"""Bot, sleeve, and presence state table ownership."""

from typing import Final

TABLES: Final[frozenset[str]] = frozenset({"bot_state", "sleeve_state", "presence"})
