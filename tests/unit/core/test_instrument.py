"""Unit contracts for the immutable Instrument domain model."""

from decimal import Decimal
from itertools import product
from typing import Literal

import pytest
from pydantic import ValidationError

from omra.core import (
    EQUITY_CLASSES,
    IdentifierError,
    Instrument,
    InvariantViolation,
    Market,
    TickRuleId,
)
from omra.core.models import Market as ModelsMarket

Currency = Literal["KRW", "USD"]

_CURRENCIES: tuple[Currency, ...] = ("KRW", "USD")
_LOT_STEPS = (Decimal(1), Decimal("1e-8"))
_VENUE_CASES = tuple(product(tuple(Market), _CURRENCIES, tuple(TickRuleId), _LOT_STEPS))


def _symbol(market: Market) -> str:
    if market is Market.KRX:
        return "069500"
    if market is Market.UPBIT:
        return "KRW-BTC"
    return "VTI"


def _is_canonical_combination(
    market: Market,
    currency: Currency,
    tick_rule: TickRuleId,
    lot_step: Decimal,
) -> bool:
    if market is Market.KRX:
        return (
            currency == "KRW"
            and tick_rule in {TickRuleId.KRX_ETF_5, TickRuleId.KRX7}
            and lot_step == 1
        )
    if market is Market.UPBIT:
        return currency == "KRW" and tick_rule is TickRuleId.UPBIT and lot_step == Decimal("1e-8")
    return currency == "USD" and tick_rule is TickRuleId.USD_PENNY and lot_step == 1


@pytest.mark.parametrize(("market", "currency", "tick_rule", "lot_step"), _VENUE_CASES)
def test_instrument_accepts_only_canonical_venue_combinations(
    market: Market,
    currency: Currency,
    tick_rule: TickRuleId,
    lot_step: Decimal,
) -> None:
    values = {
        "symbol": _symbol(market),
        "market": market,
        "currency": currency,
        "asset_class": "crypto" if market is Market.UPBIT else "us_etf_equity",
        "lot_step": lot_step,
        "tick_rule": tick_rule,
    }

    if _is_canonical_combination(market, currency, tick_rule, lot_step):
        instrument = Instrument.model_validate(values)
        assert instrument.key == f"{market.value}:{_symbol(market)}"
    else:
        with pytest.raises(InvariantViolation):
            Instrument.model_validate(values)


def test_instrument_is_hashable_frozen_strict_and_reexports_market() -> None:
    instrument = Instrument(
        symbol="VTI",
        market=Market.NASD,
        currency="USD",
        asset_class="us_etf_equity",
        lot_step=Decimal(1),
        tick_rule=TickRuleId.USD_PENNY,
    )

    assert ModelsMarket is Market
    assert {instrument: instrument.key}[instrument] == "NASD:VTI"

    field_name = "symbol"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(instrument, field_name, "VOO")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Instrument.model_validate(
            {**instrument.model_dump(), "display_name": "Vanguard Total Market"}
        )


def test_instrument_rejects_float_lot_step_at_the_domain_boundary() -> None:
    with pytest.raises(ValidationError, match="float input is forbidden"):
        Instrument.model_validate(
            {
                "symbol": "VTI",
                "market": "NASD",
                "currency": "USD",
                "asset_class": "us_etf_equity",
                "lot_step": 1.0,
                "tick_rule": "usd_penny",
            }
        )


@pytest.mark.parametrize("symbol", ["", "KRW BTC"])
def test_instrument_rejects_noncanonical_symbol_on_creation(symbol: str) -> None:
    with pytest.raises(IdentifierError):
        Instrument(
            symbol=symbol,
            market=Market.UPBIT,
            currency="KRW",
            asset_class="crypto",
            lot_step=Decimal("1e-8"),
            tick_rule=TickRuleId.UPBIT,
        )


def test_equity_class_catalog_matches_the_portfolio_contract() -> None:
    assert frozenset({"kr_etf_equity", "us_etf_equity", "us_stock"}) == EQUITY_CLASSES
