"""`core.ids` — 단조 내부 ID와 exact-match 종목 키.

검증 항목: 설계 02 §3.1~§3.2
"""

from __future__ import annotations

import string

import pytest

from omra import core
from omra.core import ids
from omra.core.errors import IdentifierError
from omra.core.ids import Market, instrument_key, new_id, parse_instrument_key


def test_new_id_generates_one_million_ids_in_strict_lexicographic_order() -> None:
    """단조 정책이 깨지면 감사·주문 ID 정렬이 발급 순서를 잃는다."""
    previous = new_id()
    for _ in range(999_999):
        current = new_id()
        assert previous < current
        previous = current


def test_new_id_uses_26_character_crockford_alphabet() -> None:
    """ULID 표기 문자가 흔들리면 DB TEXT 키와 외부 감사 grep 규약이 깨진다."""
    value = new_id()
    alphabet = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert len(value) == 26
    assert set(value) <= alphabet
    assert set(string.ascii_lowercase).isdisjoint(value)


def test_market_values_are_exact_contract_set() -> None:
    """시장 값은 종목 키의 venue 부분이므로 alias 추가도 계약 변경이다."""
    assert [m.value for m in Market] == ["KRX", "NASD", "NYSE", "AMEX", "UPBIT"]


@pytest.mark.parametrize(
    ("market", "symbol", "expected"),
    [
        (Market.KRX, "278530", "KRX:278530"),
        (Market.NASD, "VTI", "NASD:VTI"),
        (Market.UPBIT, "KRW-BTC", "UPBIT:KRW-BTC"),
    ],
)
def test_instrument_key_roundtrip(market: Market, symbol: str, expected: str) -> None:
    assert instrument_key(market, symbol) == expected
    assert parse_instrument_key(expected) == (market, symbol)


def test_parse_instrument_key_splits_only_at_the_first_colon() -> None:
    """심볼 본문은 exact-match 대상이라 뒤쪽 콜론을 손대지 않는다."""
    assert parse_instrument_key("NASD:BRK:B") == (Market.NASD, "BRK:B")


def test_upbit_hyphen_is_preserved_verbatim() -> None:
    assert instrument_key(Market.UPBIT, "KRW-BTC") == "UPBIT:KRW-BTC"


@pytest.mark.parametrize(
    "bad",
    ["KRX278530", "UNKNOWN:VTI", "KRX:", "krx:278530", "KRX: 278530"],
)
def test_parse_instrument_key_rejects_all_five_invalid_forms(bad: str) -> None:
    with pytest.raises(IdentifierError):
        parse_instrument_key(bad)


@pytest.mark.parametrize("bad", ["", " ", "VT I", "VTI\n", "\tVTI", 123])
def test_instrument_key_rejects_empty_non_string_or_whitespace_symbol(bad: object) -> None:
    with pytest.raises(IdentifierError):
        instrument_key(Market.NASD, bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["", " ", "KRX:278530\n", "KRX:\t278530", 123])
def test_parse_instrument_key_rejects_non_string_or_whitespace_key(bad: object) -> None:
    with pytest.raises(IdentifierError):
        parse_instrument_key(bad)  # type: ignore[arg-type]


def test_ids_module_public_exports_are_exact() -> None:
    """공개 API가 늘면 ULID 생성 우회 또는 fuzzy key helper가 생길 수 있다."""
    assert ids.__all__ == [
        "Market",
        "instrument_key",
        "new_id",
        "parse_instrument_key",
    ]


def test_core_reexports_market_only_from_ids() -> None:
    assert core.Market is Market
    assert "new_id" not in dir(core)
