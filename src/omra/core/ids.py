"""단조 내부 식별자와 exact-match 종목 키.

`new_id()`는 옴라 내부 ULID 생성의 단일 진입점이다. 종목 키는
`"{market}:{symbol}"` 형식의 문자열로만 비교하며, 대소문자 정규화·공백 제거·
별칭 매칭을 하지 않는다.

정본: 설계 02 §3.1~§3.2 [DD-02-1·2]
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from ulid import ULIDGenerator

from omra.core.errors import IdentifierError

__all__ = [
    "Market",
    "instrument_key",
    "new_id",
    "parse_instrument_key",
]

_GENERATOR: Final = ULIDGenerator()


class Market(StrEnum):
    KRX = "KRX"
    NASD = "NASD"
    NYSE = "NYSE"
    AMEX = "AMEX"
    UPBIT = "UPBIT"


def new_id() -> str:
    return str(_GENERATOR.generate())


def _validate_symbol(symbol: object) -> str:
    if not isinstance(symbol, str):
        raise IdentifierError("종목 심볼은 문자열이어야 한다", symbol_type=type(symbol).__name__)
    if not symbol:
        raise IdentifierError("종목 심볼은 비어 있을 수 없다")
    if any(ch.isspace() for ch in symbol):
        raise IdentifierError("종목 심볼에는 공백 문자가 들어갈 수 없다", symbol=symbol)
    return symbol


def instrument_key(market: Market, symbol: str) -> str:
    valid_symbol = _validate_symbol(symbol)
    return f"{market.value}:{valid_symbol}"


def parse_instrument_key(key: str) -> tuple[Market, str]:
    if not isinstance(key, str):
        raise IdentifierError("종목 키는 문자열이어야 한다", key_type=type(key).__name__)
    if any(ch.isspace() for ch in key):
        raise IdentifierError("종목 키에는 공백 문자가 들어갈 수 없다", key=key)

    venue, sep, symbol = key.partition(":")
    if sep == "":
        raise IdentifierError("종목 키에는 시장과 심볼 구분자 ':'가 필요하다", key=key)

    try:
        market = Market(venue)
    except ValueError as exc:
        raise IdentifierError("알 수 없는 시장 식별자", market=venue) from exc

    return market, _validate_symbol(symbol)
