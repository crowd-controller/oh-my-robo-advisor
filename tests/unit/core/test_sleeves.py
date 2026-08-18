"""Unit contracts for broker-by-market sleeve mapping."""

from decimal import Decimal

import pytest

from omra.core import (
    US_MARKETS,
    Account,
    AccountMode,
    AccountType,
    Broker,
    IdentifierError,
    Instrument,
    Market,
    SleeveId,
    TickRuleId,
    sleeve_of,
)

_SLEEVE_CASES = (
    (Broker.KIS, Market.KRX, SleeveId.KIS_DOMESTIC),
    (Broker.KIS, Market.NASD, SleeveId.KIS_OVERSEAS),
    (Broker.KIS, Market.NYSE, SleeveId.KIS_OVERSEAS),
    (Broker.KIS, Market.AMEX, SleeveId.KIS_OVERSEAS),
    (Broker.KIS, Market.UPBIT, None),
    (Broker.UPBIT, Market.KRX, SleeveId.UPBIT),
    (Broker.UPBIT, Market.NASD, SleeveId.UPBIT),
    (Broker.UPBIT, Market.NYSE, SleeveId.UPBIT),
    (Broker.UPBIT, Market.AMEX, SleeveId.UPBIT),
    (Broker.UPBIT, Market.UPBIT, SleeveId.UPBIT),
)


def _instrument(market: Market) -> Instrument:
    if market is Market.KRX:
        return Instrument(
            symbol="069500",
            market=market,
            currency="KRW",
            asset_class="kr_etf_equity",
            lot_step=Decimal(1),
            tick_rule=TickRuleId.KRX_ETF_5,
        )
    if market is Market.UPBIT:
        return Instrument(
            symbol="KRW-BTC",
            market=market,
            currency="KRW",
            asset_class="crypto",
            lot_step=Decimal("1e-8"),
            tick_rule=TickRuleId.UPBIT,
        )
    return Instrument(
        symbol="VTI",
        market=market,
        currency="USD",
        asset_class="us_etf_equity",
        lot_step=Decimal(1),
        tick_rule=TickRuleId.USD_PENNY,
    )


@pytest.mark.parametrize(("broker", "market", "expected"), _SLEEVE_CASES)
def test_sleeve_of_follows_canonical_broker_first_priority(
    broker: Broker,
    market: Market,
    expected: SleeveId | None,
) -> None:
    account = Account(
        id="upbit_01" if broker is Broker.UPBIT else "general_01",
        type=AccountType.UPBIT if broker is Broker.UPBIT else AccountType.GENERAL,
        broker=broker,
        mode=AccountMode.AUTO,
    )

    if expected is None:
        with pytest.raises(IdentifierError):
            sleeve_of(account, _instrument(market))
    else:
        assert sleeve_of(account, _instrument(market)) is expected


def test_us_market_catalog_is_exact() -> None:
    assert frozenset({Market.NASD, Market.NYSE, Market.AMEX}) == US_MARKETS
