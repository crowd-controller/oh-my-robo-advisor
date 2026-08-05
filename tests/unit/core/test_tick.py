"""`core.tick` — 호가단위 정규화와 재호가 산술.

검증 항목: 설계 02 §6 [DD-02-7·8]
"""

from __future__ import annotations

from decimal import Decimal, DecimalException, localcontext

import pytest

from omra.core import tick
from omra.core.errors import InvariantViolation, TickRuleError
from omra.core.tick import (
    TickRuleId,
    is_aligned,
    next_down,
    next_up,
    snap_buy,
    snap_sell,
    tick_size,
    ticks_between,
)


def _d(value: str) -> Decimal:
    return Decimal(value)


def test_public_exports_are_exact() -> None:
    assert tick.__all__ == [
        "TickRuleId",
        "is_aligned",
        "next_down",
        "next_up",
        "snap_buy",
        "snap_sell",
        "tick_size",
        "ticks_between",
    ]


def test_tick_rule_values_are_exact_contract_set() -> None:
    assert [r.value for r in TickRuleId] == [
        "krx_etf_5",
        "krx7",
        "usd_penny",
        "upbit",
    ]


@pytest.mark.parametrize(
    ("price", "rule", "expected"),
    [
        (_d("5"), TickRuleId.KRX_ETF_5, _d("5")),
        (_d("12345"), TickRuleId.KRX_ETF_5, _d("5")),
        (_d("1"), TickRuleId.USD_PENNY, _d("0.01")),
        (_d("123.45"), TickRuleId.USD_PENNY, _d("0.01")),
    ],
)
def test_confirmed_tick_sizes(price: Decimal, rule: TickRuleId, expected: Decimal) -> None:
    assert tick_size(price, rule) == expected


@pytest.mark.parametrize(
    "api",
    [tick_size, snap_buy, snap_sell, next_up, next_down, is_aligned],
)
@pytest.mark.parametrize("bad", [1, 1.0, True, "1"])
def test_one_price_public_apis_share_decimal_only_validation(api: object, bad: object) -> None:
    with pytest.raises(TickRuleError, match="Decimal"):
        api(bad, TickRuleId.KRX_ETF_5)  # type: ignore[operator]


@pytest.mark.parametrize(
    ("lo", "hi"),
    [(1, _d("10")), (_d("10"), 15), (True, _d("10")), (_d("10"), "15")],
)
def test_ticks_between_validates_both_endpoints_as_decimals(lo: object, hi: object) -> None:
    with pytest.raises(TickRuleError, match="Decimal"):
        ticks_between(lo, hi, TickRuleId.KRX_ETF_5)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [_d("0"), _d("-1"), _d("NaN"), _d("Infinity"), _d("-Infinity")])
def test_prices_must_be_positive_and_finite(bad: Decimal) -> None:
    with pytest.raises(TickRuleError):
        tick_size(bad, TickRuleId.KRX_ETF_5)


@pytest.mark.parametrize(
    "api",
    [tick_size, snap_buy, snap_sell, next_up, next_down, is_aligned],
)
def test_usd_penny_rejects_sub_dollar_inputs(api: object) -> None:
    with pytest.raises(TickRuleError, match="1 USD"):
        api(_d("0.99"), TickRuleId.USD_PENNY)  # type: ignore[operator]


def test_ticks_between_rejects_sub_dollar_usd_endpoint() -> None:
    with pytest.raises(TickRuleError, match="1 USD"):
        ticks_between(_d("0.99"), _d("1.00"), TickRuleId.USD_PENNY)


@pytest.mark.parametrize(
    ("price", "rule", "buy", "sell"),
    [
        (_d("12"), TickRuleId.KRX_ETF_5, _d("10"), _d("15")),
        (_d("15"), TickRuleId.KRX_ETF_5, _d("15"), _d("15")),
        (_d("123.456"), TickRuleId.USD_PENNY, _d("123.45"), _d("123.46")),
        (_d("123.45"), TickRuleId.USD_PENNY, _d("123.45"), _d("123.45")),
    ],
)
def test_snap_buy_floors_and_snap_sell_ceilings(
    price: Decimal, rule: TickRuleId, buy: Decimal, sell: Decimal
) -> None:
    assert snap_buy(price, rule) == buy
    assert snap_sell(price, rule) == sell


@pytest.mark.parametrize("api", [snap_buy, next_down])
def test_results_that_would_be_non_positive_fail_closed(api: object) -> None:
    with pytest.raises(TickRuleError, match="0 이하"):
        api(_d("1"), TickRuleId.KRX_ETF_5)  # type: ignore[operator]


@pytest.mark.parametrize(
    ("price", "rule", "expected"),
    [
        (_d("10"), TickRuleId.KRX_ETF_5, True),
        (_d("11"), TickRuleId.KRX_ETF_5, False),
        (_d("1.00"), TickRuleId.USD_PENNY, True),
        (_d("1.001"), TickRuleId.USD_PENNY, False),
    ],
)
def test_is_aligned(price: Decimal, rule: TickRuleId, expected: bool) -> None:
    assert is_aligned(price, rule) is expected


@pytest.mark.parametrize(
    ("price", "rule", "up", "down"),
    [
        (_d("12"), TickRuleId.KRX_ETF_5, _d("15"), _d("10")),
        (_d("15"), TickRuleId.KRX_ETF_5, _d("20"), _d("10")),
        (_d("123.456"), TickRuleId.USD_PENNY, _d("123.46"), _d("123.45")),
        (_d("123.45"), TickRuleId.USD_PENNY, _d("123.46"), _d("123.44")),
    ],
)
def test_next_up_and_next_down(
    price: Decimal, rule: TickRuleId, up: Decimal, down: Decimal
) -> None:
    assert next_up(price, rule) == up
    assert next_down(price, rule) == down


def test_next_down_rejects_below_minimum_usd_result() -> None:
    with pytest.raises(TickRuleError, match="1 USD"):
        next_down(_d("1.00"), TickRuleId.USD_PENNY)


def test_ticks_between_accepts_equal_aligned_endpoints() -> None:
    assert ticks_between(_d("10"), _d("10"), TickRuleId.KRX_ETF_5) == 0


def test_ticks_between_counts_three_uniform_steps() -> None:
    p = _d("15")
    hi = next_up(
        next_up(next_up(p, TickRuleId.KRX_ETF_5), TickRuleId.KRX_ETF_5), TickRuleId.KRX_ETF_5
    )
    assert hi == _d("30")
    assert ticks_between(p, hi, TickRuleId.KRX_ETF_5) == 3


def test_large_finite_aligned_price_is_context_independent_for_krx_tick_math() -> None:
    price = _d("1000000000000000000000000000")
    one_tick_up = _d("1000000000000000000000000005")
    three_ticks_up = _d("1000000000000000000000000015")
    one_tick_down = _d("999999999999999999999999995")

    with localcontext() as ctx:
        ctx.prec = 1

        assert snap_buy(price, TickRuleId.KRX_ETF_5) == price
        assert snap_sell(price, TickRuleId.KRX_ETF_5) == price
        assert is_aligned(price, TickRuleId.KRX_ETF_5)
        assert next_up(price, TickRuleId.KRX_ETF_5) == one_tick_up
        assert next_down(price, TickRuleId.KRX_ETF_5) == one_tick_down
        assert ticks_between(price, three_ticks_up, TickRuleId.KRX_ETF_5) == 3


def test_decimal_arithmetic_context_failures_do_not_leak_raw_decimal_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_precision(*_values: Decimal) -> int:
        return 0

    monkeypatch.setattr(tick, "_required_precision", invalid_precision)
    with pytest.raises(TickRuleError) as exc_info:
        snap_buy(_d("5"), TickRuleId.KRX_ETF_5)

    assert not isinstance(exc_info.value, DecimalException)
    assert exc_info.value.__cause__ is not None


def test_ticks_between_rejects_off_grid_endpoint() -> None:
    with pytest.raises(TickRuleError, match="격자"):
        ticks_between(_d("10"), _d("12"), TickRuleId.KRX_ETF_5)


def test_ticks_between_rejects_inverted_range_as_invariant_violation() -> None:
    with pytest.raises(InvariantViolation):
        ticks_between(_d("15"), _d("10"), TickRuleId.KRX_ETF_5)


@pytest.mark.parametrize("rule", [TickRuleId.KRX7, TickRuleId.UPBIT])
@pytest.mark.parametrize(
    "api",
    [tick_size, snap_buy, snap_sell, next_up, next_down, is_aligned],
)
def test_unconfirmed_ladder_rules_fail_closed(rule: TickRuleId, api: object) -> None:
    with pytest.raises(TickRuleError, match="확인 필요"):
        api(_d("1000"), rule)  # type: ignore[operator]


@pytest.mark.parametrize("rule", [TickRuleId.KRX7, TickRuleId.UPBIT])
def test_unconfirmed_ladder_ticks_between_fails_closed(rule: TickRuleId) -> None:
    with pytest.raises(TickRuleError, match="확인 필요"):
        ticks_between(_d("1000"), _d("1010"), rule)


def test_synthetic_ladder_tick_size_and_snapping_without_exchange_facts() -> None:
    ladder = ((_d("0"), _d("5")), (_d("100"), _d("10")), (_d("500"), _d("50")))

    assert tick._tick_size_from_ladder(_d("99"), ladder) == _d("5")
    assert tick._tick_size_from_ladder(_d("100"), ladder) == _d("10")
    assert tick._snap_buy_from_ladder(_d("99"), ladder) == _d("95")
    assert tick._snap_sell_from_ladder(_d("96"), ladder) == _d("100")


def test_synthetic_ladder_next_movement_without_exchange_facts() -> None:
    ladder = ((_d("0"), _d("5")), (_d("100"), _d("10")), (_d("500"), _d("50")))

    assert tick._next_up_from_ladder(_d("99"), ladder) == _d("100")
    assert tick._next_down_from_ladder(_d("96"), ladder) == _d("95")
    assert tick._next_down_from_ladder(_d("100"), ladder) == _d("95")


def test_synthetic_ladder_ticks_between_without_exchange_facts() -> None:
    ladder = ((_d("0"), _d("5")), (_d("100"), _d("10")), (_d("500"), _d("50")))

    assert tick._ticks_between_from_ladder(_d("95"), _d("110"), ladder) == 2


def test_synthetic_ladder_clamps_next_up_overjump_to_misaligned_boundary() -> None:
    ladder = ((_d("0"), _d("5")), (_d("103"), _d("10")))

    assert tick._next_up_from_ladder(_d("102"), ladder) == _d("103")


def test_synthetic_ladder_next_down_uses_previous_grid_at_misaligned_boundary() -> None:
    ladder = ((_d("0"), _d("5")), (_d("103"), _d("10")))

    assert tick._next_down_from_ladder(_d("103"), ladder) == _d("100")


def test_synthetic_ladder_ticks_between_counts_misaligned_boundary_clamp() -> None:
    ladder = ((_d("0"), _d("5")), (_d("103"), _d("10")))

    assert tick._ticks_between_from_ladder(_d("100"), _d("103"), ladder) == 1


@pytest.mark.parametrize(
    "ladder",
    [
        (),
        ((1, _d("5")),),
        ((_d("0"), 5),),
        ((_d("NaN"), _d("5")),),
        ((_d("0"), _d("Infinity")),),
        ((_d("-1"), _d("5")),),
        ((_d("0"), _d("0")),),
        ((_d("0"), _d("-1")),),
        ((_d("0"), _d("5")), (_d("0"), _d("10"))),
        ((_d("100"), _d("5")),),
    ],
)
def test_synthetic_ladder_validation_rejects_malformed_values(ladder: object) -> None:
    with pytest.raises(TickRuleError):
        tick._tick_size_from_ladder(_d("1"), ladder)  # type: ignore[arg-type]


_KRX7_OFFICIAL_BOUNDARY_CASES: tuple[tuple[Decimal, Decimal, Decimal, Decimal], ...] = ()
_UPBIT_OFFICIAL_BOUNDARY_CASES: tuple[tuple[Decimal, Decimal, Decimal, Decimal], ...] = ()


@pytest.mark.xfail(strict=True, reason="KRX7 공식 구간표 확정 전 경계 스캐폴드")
def test_krx7_official_boundary_vectors_are_ready_for_activation() -> None:
    assert _KRX7_OFFICIAL_BOUNDARY_CASES
    for price, expected_tick, expected_up, expected_down in _KRX7_OFFICIAL_BOUNDARY_CASES:
        assert tick_size(price, TickRuleId.KRX7) == expected_tick
        assert next_up(price, TickRuleId.KRX7) == expected_up
        assert next_down(price, TickRuleId.KRX7) == expected_down


@pytest.mark.xfail(strict=True, reason="Upbit 공식 구간표 확정 전 경계 스캐폴드")
def test_upbit_official_boundary_vectors_are_ready_for_activation() -> None:
    assert _UPBIT_OFFICIAL_BOUNDARY_CASES
    for price, expected_tick, expected_up, expected_down in _UPBIT_OFFICIAL_BOUNDARY_CASES:
        assert tick_size(price, TickRuleId.UPBIT) == expected_tick
        assert next_up(price, TickRuleId.UPBIT) == expected_up
        assert next_down(price, TickRuleId.UPBIT) == expected_down
