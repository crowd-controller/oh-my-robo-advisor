"""`core.models` 1차 — Instrument와 주문 enum 계약.

검증 항목: 설계 02 §4·§7.1~§7.2 [DD-02-4·5·6·17·19], 진행표 S03-2.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from itertools import product

import pytest
from pydantic import ValidationError

from omra.core import models
from omra.core.errors import InvariantViolation
from omra.core.ids import Market, instrument_key
from omra.core.models import (
    EQUITY_CLASSES,
    Instrument,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    PlanReason,
)
from omra.core.tick import TickRuleId

_CURRENCIES = ("KRW", "USD")
_LOT_STEPS = (Decimal("1"), Decimal("1e-8"))
_SYMBOLS = {
    Market.KRX: "069500",
    Market.NASD: "VTI",
    Market.NYSE: "VOO",
    Market.AMEX: "SPY",
    Market.UPBIT: "KRW-BTC",
}
_VALID_COMBINATIONS = frozenset(
    {
        (Market.KRX, "KRW", TickRuleId.KRX_ETF_5, Decimal("1")),
        (Market.KRX, "KRW", TickRuleId.KRX7, Decimal("1")),
        (Market.NASD, "USD", TickRuleId.USD_PENNY, Decimal("1")),
        (Market.NYSE, "USD", TickRuleId.USD_PENNY, Decimal("1")),
        (Market.AMEX, "USD", TickRuleId.USD_PENNY, Decimal("1")),
        (Market.UPBIT, "KRW", TickRuleId.UPBIT, Decimal("1e-8")),
    }
)
_ALL_COMBINATIONS = tuple(product(Market, _CURRENCIES, TickRuleId, _LOT_STEPS))


def _instrument(
    market: Market,
    currency: str,
    tick_rule: TickRuleId,
    lot_step: Decimal,
) -> Instrument:
    return Instrument(
        symbol=_SYMBOLS[market],
        market=market,
        currency=currency,
        asset_class="test_asset_class",
        lot_step=lot_step,
        tick_rule=tick_rule,
    )


def test_models_public_exports_are_exact_s03_2_surface() -> None:
    assert models.__all__ == [
        "EQUITY_CLASSES",
        "Instrument",
        "Market",
        "OrderIntent",
        "OrderSide",
        "OrderStatus",
        "OrderType",
        "PlanReason",
    ]


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    [
        (OrderSide, [("BUY", "BUY"), ("SELL", "SELL")]),
        (
            OrderType,
            [
                ("LIMIT", "LIMIT"),
                ("MARKET", "MARKET"),
                ("LOO", "LOO"),
                ("MOO", "MOO"),
                ("LOC", "LOC"),
                ("MOC", "MOC"),
            ],
        ),
        (
            OrderStatus,
            [
                ("SUBMITTING", "SUBMITTING"),
                ("PENDING", "PENDING"),
                ("PARTIALLY_FILLED", "PARTIALLY_FILLED"),
                ("FILLED", "FILLED"),
                ("CANCELLED", "CANCELLED"),
                ("REJECTED", "REJECTED"),
                ("EXPIRED", "EXPIRED"),
                ("EXPIRED_UNKNOWN", "EXPIRED_UNKNOWN"),
            ],
        ),
        (
            OrderIntent,
            [
                ("BAND_RESTORE", "band_restore"),
                ("CLASS_BAND", "class_band"),
                ("CASHFLOW", "cashflow"),
                ("HARVEST", "harvest"),
                ("E7_TRANSFER", "e7_transfer"),
                ("CONSTRAINT_CURE", "constraint_cure"),
                ("CRYPTO_SLEEVE", "crypto_sleeve"),
                ("SATELLITE_DD", "satellite_dd"),
                ("TARGET_SHIFT", "target_shift"),
                ("WITHDRAWAL", "withdrawal"),
                ("MANUAL", "manual"),
            ],
        ),
        (
            PlanReason,
            [
                ("DRIFT_BAND", "drift_band"),
                ("CASHFLOW", "cashflow"),
                ("HARVEST", "harvest"),
                ("MANUAL", "manual"),
                ("E7_TRANSFER", "e7_transfer"),
            ],
        ),
    ],
)
def test_order_enums_are_exact_str_enum_snapshots(
    enum_type: type[StrEnum],
    expected: list[tuple[str, str]],
) -> None:
    assert issubclass(enum_type, StrEnum)
    assert enum_type.__module__ == "omra.core.models"
    assert [(member.name, member.value) for member in enum_type] == expected
    assert list(enum_type.__members__) == [name for name, _ in expected]


def test_equity_classes_are_exact_contract_snapshot() -> None:
    assert frozenset({"kr_etf_equity", "us_etf_equity", "us_stock"}) == EQUITY_CLASSES


@pytest.mark.parametrize(("market", "currency", "tick_rule", "lot_step"), _ALL_COMBINATIONS)
def test_instrument_cross_validation_table_is_exhaustive(
    market: Market,
    currency: str,
    tick_rule: TickRuleId,
    lot_step: Decimal,
) -> None:
    combination = (market, currency, tick_rule, lot_step)
    if combination in _VALID_COMBINATIONS:
        instrument = _instrument(*combination)
        assert instrument.key == instrument_key(market, _SYMBOLS[market])
    else:
        with pytest.raises(InvariantViolation):
            _instrument(*combination)


@pytest.mark.parametrize("bad_lot_step", [1.0, True])
def test_instrument_rejects_float_and_bool_lot_steps(bad_lot_step: float | bool) -> None:
    with pytest.raises(ValidationError):
        Instrument(
            symbol="069500",
            market=Market.KRX,
            currency="KRW",
            asset_class="kr_etf_equity",
            lot_step=bad_lot_step,
            tick_rule=TickRuleId.KRX_ETF_5,
        )


def test_instrument_is_frozen_hashable_and_uses_full_field_equality() -> None:
    instrument = _instrument(Market.KRX, "KRW", TickRuleId.KRX_ETF_5, Decimal("1"))
    same = instrument.model_copy()
    different_class = instrument.model_copy(update={"asset_class": "kr_etf_bond"})

    assert instrument == same
    assert hash(instrument) == hash(same)
    assert instrument != different_class
    assert {instrument, same, different_class} == {instrument, different_class}

    with pytest.raises(ValidationError) as exc_info:
        instrument.symbol = "229200"  # type: ignore[misc]  # deliberate frozen violation
    assert exc_info.value.errors()[0]["type"] == "frozen_instance"


def test_models_reexports_market_from_ids_without_duplicate_type() -> None:
    assert models.Market is Market
