"""Exact, broker-neutral instrument identifier rules."""

from enum import StrEnum

from ulid import ULIDGenerator

from omra.core.errors import IdentifierError

_ULID_GENERATOR = ULIDGenerator()


def new_id() -> str:
    """Return a process-monotonic 26-character ULID."""
    return str(_ULID_GENERATOR.generate())


class Market(StrEnum):
    """Canonical execution venues used in instrument keys."""

    KRX = "KRX"
    NASD = "NASD"
    NYSE = "NYSE"
    AMEX = "AMEX"
    UPBIT = "UPBIT"


def _validated_symbol(symbol: str) -> str:
    if not symbol or any(character.isspace() for character in symbol):
        raise IdentifierError(
            "instrument symbol must be non-empty and contain no whitespace",
            context={"symbol": symbol},
        )
    return symbol


def instrument_key(market: Market, symbol: str) -> str:
    """Build the only normalized key used for exact instrument matching."""
    return f"{market.value}:{_validated_symbol(symbol)}"


def parse_instrument_key(key: str) -> tuple[Market, str]:
    """Parse a normalized instrument key or fail without a fuzzy fallback."""
    venue, separator, symbol = key.partition(":")
    if not separator:
        raise IdentifierError(
            "instrument key must contain a venue separator",
            context={"instrument_key": key},
        )
    try:
        market = Market(venue)
    except ValueError as error:
        raise IdentifierError(
            "instrument key contains an unknown venue",
            context={"instrument_key": key, "venue": venue},
        ) from error
    return market, _validated_symbol(symbol)
