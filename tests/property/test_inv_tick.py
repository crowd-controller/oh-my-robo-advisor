"""`core.tick` property 불변식.

검증 항목: 설계 02 §6.5
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from omra.core.tick import (
    TickRuleId,
    is_aligned,
    next_down,
    next_up,
    snap_buy,
    snap_sell,
    ticks_between,
)

KRX_ALIGNED = st.integers(min_value=1, max_value=2_000_000).map(lambda n: Decimal(n * 5))
KRX_PRICE = st.decimals(
    min_value=Decimal("5"),
    max_value=Decimal("10000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
USD_ALIGNED = st.integers(min_value=100, max_value=1_000_000).map(lambda n: Decimal(n) / 100)
USD_PRICE = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("10000.00"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


@given(price=KRX_PRICE)
def test_krx_etf_snaps_bracket_price_and_remain_aligned(price: Decimal) -> None:
    buy = snap_buy(price, TickRuleId.KRX_ETF_5)
    sell = snap_sell(price, TickRuleId.KRX_ETF_5)

    assert buy <= price <= sell
    assert is_aligned(buy, TickRuleId.KRX_ETF_5)
    assert is_aligned(sell, TickRuleId.KRX_ETF_5)
    assert next_up(price, TickRuleId.KRX_ETF_5) > price
    assert next_down(next_up(price, TickRuleId.KRX_ETF_5), TickRuleId.KRX_ETF_5) == buy


@given(price=USD_PRICE)
def test_usd_penny_snaps_bracket_price_and_remain_aligned(price: Decimal) -> None:
    buy = snap_buy(price, TickRuleId.USD_PENNY)
    sell = snap_sell(price, TickRuleId.USD_PENNY)

    assert buy <= price <= sell
    assert is_aligned(buy, TickRuleId.USD_PENNY)
    assert is_aligned(sell, TickRuleId.USD_PENNY)
    assert next_up(price, TickRuleId.USD_PENNY) > price
    assert next_down(next_up(price, TickRuleId.USD_PENNY), TickRuleId.USD_PENNY) == buy


@given(price=KRX_ALIGNED)
def test_krx_etf_ticks_between_three_next_up_steps(price: Decimal) -> None:
    hi = next_up(
        next_up(next_up(price, TickRuleId.KRX_ETF_5), TickRuleId.KRX_ETF_5),
        TickRuleId.KRX_ETF_5,
    )

    assert ticks_between(price, hi, TickRuleId.KRX_ETF_5) == 3


@given(price=USD_ALIGNED)
def test_usd_penny_ticks_between_three_next_up_steps(price: Decimal) -> None:
    hi = next_up(
        next_up(next_up(price, TickRuleId.USD_PENNY), TickRuleId.USD_PENNY),
        TickRuleId.USD_PENNY,
    )

    assert ticks_between(price, hi, TickRuleId.USD_PENNY) == 3
