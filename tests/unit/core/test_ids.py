"""Unit contracts for exact instrument identifiers."""

import re

import pytest

from omra.core import (
    IdentifierError,
    Market,
    TickRuleId,
    instrument_key,
    new_id,
    parse_instrument_key,
)

_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def test_market_and_tick_rule_values_match_canonical_vocabulary() -> None:
    assert [member.value for member in Market] == ["KRX", "NASD", "NYSE", "AMEX", "UPBIT"]
    assert [member.value for member in TickRuleId] == [
        "krx_etf_5",
        "krx7",
        "usd_penny",
        "upbit",
    ]


@pytest.mark.parametrize(
    ("key", "market", "symbol"),
    [
        ("KRX:278530", Market.KRX, "278530"),
        ("NASD:VTI", Market.NASD, "VTI"),
        ("UPBIT:KRW-BTC", Market.UPBIT, "KRW-BTC"),
    ],
)
def test_instrument_key_round_trips_exactly(key: str, market: Market, symbol: str) -> None:
    assert instrument_key(market, symbol) == key
    assert parse_instrument_key(key) == (market, symbol)


@pytest.mark.parametrize(
    "key",
    ["KRX278530", "UNKNOWN:VTI", "KRX:", "krx:278530", "KRX:27 8530"],
)
def test_parse_instrument_key_rejects_every_malformed_shape(key: str) -> None:
    with pytest.raises(IdentifierError):
        parse_instrument_key(key)


@pytest.mark.parametrize("symbol", ["", " ", "V TI", "VTI\n"])
def test_instrument_key_rejects_empty_or_whitespace_symbols(symbol: str) -> None:
    with pytest.raises(IdentifierError):
        instrument_key(Market.NASD, symbol)


def test_new_id_is_unique_and_lexicographically_monotonic_for_one_million_issues() -> None:
    previous = ""

    for _ in range(1_000_000):
        current = new_id()
        assert len(current) == 26
        assert _ULID_PATTERN.fullmatch(current)
        assert current > previous
        previous = current
