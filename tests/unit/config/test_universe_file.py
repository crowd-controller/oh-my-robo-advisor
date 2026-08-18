"""Unit and table contracts for the universe record schema."""

from datetime import date
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError
from omra.config.files import RecordFile, UniverseFile, UniverseInstrument
from omra.core import Instrument, Market, TickRuleId

Currency = Literal["KRW", "USD"]

_ASSET_CLASS_WORDS = (
    "kr_etf_equity",
    "kr_etf_bond",
    "kr_etf_bond_ultrashort",
    "kr_etf_reit",
    "kr_etf_gold",
    "kr_etf_us_equity",
    "kr_etf_us_dividend",
    "us_etf_equity",
    "us_etf_bond",
    "us_etf_reit",
    "us_etf_gold",
    "us_etf_tips",
    "us_stock",
    "crypto",
)
_CURRENCIES: tuple[Currency, ...] = ("KRW", "USD")
_LOT_STEPS = (Decimal(1), Decimal("1e-8"))
_VENUE_CASES: tuple[tuple[Market, Currency, TickRuleId, Decimal], ...] = tuple(
    product(tuple(Market), _CURRENCIES, tuple(TickRuleId), _LOT_STEPS)
)


def _symbol(market: Market) -> str:
    if market is Market.KRX:
        return "360750"
    if market is Market.UPBIT:
        return "KRW-BTC"
    return "VTI"


def _instrument_values(
    *,
    market: Market = Market.KRX,
    currency: Currency = "KRW",
    tick_rule: TickRuleId = TickRuleId.KRX_ETF_5,
    lot_step: Decimal | float = Decimal(1),
) -> dict[str, object]:
    is_crypto = market is Market.UPBIT
    return {
        "symbol": _symbol(market),
        "market": market,
        "currency": currency,
        "asset_class": "crypto" if is_crypto else "kr_etf_equity",
        "sleeve": "crypto" if is_crypto else "core",
        "tax_inefficiency_score": 4,
        "risk_asset": not is_crypto,
        "lot_step": lot_step,
        "tick_rule": tick_rule,
        "allowed_accounts": ["general", "isa"],
        "account_preference": {"general": 1, "isa": 2},
    }


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
def test_universe_instrument_accepts_only_six_canonical_venue_combinations(
    market: Market,
    currency: Currency,
    tick_rule: TickRuleId,
    lot_step: Decimal,
) -> None:
    values = _instrument_values(
        market=market,
        currency=currency,
        tick_rule=tick_rule,
        lot_step=lot_step,
    )

    if _is_canonical_combination(market, currency, tick_rule, lot_step):
        record = UniverseInstrument.model_validate(values)
        assert record.key == f"{market.value}:{_symbol(market)}"
    else:
        with pytest.raises(ValidationError, match="market, currency, tick rule"):
            UniverseInstrument.model_validate(values)


def test_venue_table_has_eighty_candidates_and_exactly_six_valid_rows() -> None:
    assert len(_VENUE_CASES) == 80
    assert sum(_is_canonical_combination(*case) for case in _VENUE_CASES) == 6


@pytest.mark.parametrize("asset_class", _ASSET_CLASS_WORDS)
def test_asset_class_catalog_accepts_exactly_each_canonical_word(asset_class: str) -> None:
    values = _instrument_values()
    values["asset_class"] = asset_class

    assert UniverseInstrument.model_validate(values).asset_class == asset_class


@pytest.mark.parametrize(
    "asset_class",
    ["kr_etf", "KR_ETF_EQUITY", "kr_etf_equity ", "bitcoin", ""],
)
def test_asset_class_catalog_rejects_near_matches(asset_class: str) -> None:
    values = _instrument_values()
    values["asset_class"] = asset_class

    with pytest.raises(ValidationError) as raised:
        UniverseInstrument.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("asset_class",)


@pytest.mark.parametrize("score", [-1, 6])
def test_tax_inefficiency_score_rejects_values_outside_zero_to_five(score: int) -> None:
    values = _instrument_values()
    values["tax_inefficiency_score"] = score

    with pytest.raises(ValidationError):
        UniverseInstrument.model_validate(values)


def test_universe_defaults_are_conservative_and_explicit() -> None:
    record = UniverseInstrument.model_validate(_instrument_values())

    assert record.qualified_tdf is False
    assert record.proxy_index_key is None
    assert record.fx_hedged is False


def test_to_instrument_is_an_exact_core_conversion() -> None:
    record = UniverseInstrument.model_validate(_instrument_values())

    assert record.to_instrument() == Instrument(
        symbol="360750",
        market=Market.KRX,
        currency="KRW",
        asset_class="kr_etf_equity",
        lot_step=Decimal(1),
        tick_rule=TickRuleId.KRX_ETF_5,
    )
    assert record.key == "KRX:360750"


def test_universe_instrument_rejects_float_lot_step() -> None:
    values = _instrument_values(lot_step=1.0)

    with pytest.raises(ValidationError, match="float input is forbidden"):
        UniverseInstrument.model_validate(values)


@pytest.mark.parametrize("preference", [{"general": 1}, {"general": 1, "isa": 2, "irp": 3}])
def test_account_preference_keys_must_exactly_match_allowed_accounts(
    preference: dict[str, int],
) -> None:
    values = _instrument_values()
    values["account_preference"] = preference

    with pytest.raises(ValidationError, match="must exactly match"):
        UniverseInstrument.model_validate(values)


def test_universe_models_reject_unknown_fields_and_attribute_mutation() -> None:
    values = _instrument_values()
    values["display_name"] = "TIGER 미국S&P500"

    with pytest.raises(ValidationError) as extra_error:
        UniverseInstrument.model_validate(values)
    assert extra_error.value.errors()[0]["loc"] == ("display_name",)

    record = UniverseInstrument.model_validate(_instrument_values())
    instrument_field = "symbol"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(record, instrument_field, "069500")

    universe = UniverseFile(
        version=1,
        approved_at=date(2026, 8, 1),
        instruments=(record,),
    )
    universe_field = "version"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(universe, universe_field, 2)
    with pytest.raises(ValidationError) as root_extra:
        UniverseFile.model_validate({**universe.model_dump(), "owner": "operator"})
    assert root_extra.value.errors()[0]["loc"] == ("owner",)


def test_universe_file_version_and_substitute_pair_shape_are_strict() -> None:
    record = UniverseInstrument.model_validate(_instrument_values())
    base = {
        "version": 1,
        "approved_at": date(2026, 8, 1),
        "instruments": [record],
    }

    with pytest.raises(ValidationError):
        UniverseFile.model_validate({**base, "version": 0})
    with pytest.raises(ValidationError):
        UniverseFile.model_validate({**base, "approved_substitutes": [["VOO"]]})


def test_record_file_loads_normal_universe_and_preserves_defaults(tmp_path: Path) -> None:
    source = tmp_path / "universe.yaml"
    source.write_text(
        """version: 7
approved_at: 2026-08-01
instruments:
  - symbol: "360750"
    market: KRX
    currency: KRW
    asset_class: kr_etf_equity
    sleeve: core
    tax_inefficiency_score: 4
    risk_asset: true
    lot_step: 1
    tick_rule: krx_etf_5
    allowed_accounts: [general, isa, pension, irp]
    account_preference: {pension: 3, irp: 4, isa: 1, general: 2}
approved_substitutes:
  - ["VOO", "IVV"]
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, UniverseFile)

    assert loaded is not None
    assert loaded.model is UniverseFile
    assert loaded.data.version == 7
    assert loaded.data.approved_at == date(2026, 8, 1)
    assert loaded.data.approved_substitutes == (("VOO", "IVV"),)
    instrument = loaded.data.instruments[0]
    assert instrument.key == "KRX:360750"
    assert instrument.to_instrument().lot_step == Decimal(1)
    assert instrument.qualified_tdf is False
    assert instrument.proxy_index_key is None
    assert instrument.fx_hedged is False


def _write_invalid_universe(
    source: Path,
    *,
    asset_class: str = "kr_etf_equity",
    currency: Currency = "KRW",
) -> None:
    source.write_text(
        f"""version: 1
approved_at: 2026-08-01
instruments:
  - symbol: "360750"
    market: KRX
    currency: {currency}
    asset_class: {asset_class}
    sleeve: core
    tax_inefficiency_score: 4
    risk_asset: true
    lot_step: 1
    tick_rule: krx_etf_5
    allowed_accounts: [general, isa]
    account_preference: {{general: 1, isa: 2}}
""",
        encoding="utf-8",
    )


def test_record_file_reports_source_and_indexed_field_path(tmp_path: Path) -> None:
    source = tmp_path / "universe.yaml"
    _write_invalid_universe(source, asset_class="unknown")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, UniverseFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "instruments[0].asset_class"
    assert str(source) in str(raised.value)
    assert "instruments[0].asset_class" in str(raised.value)


def test_record_file_reports_index_path_for_cross_field_violation(tmp_path: Path) -> None:
    source = tmp_path / "universe.yaml"
    _write_invalid_universe(source, currency="USD")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, UniverseFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "instruments[0]"
    assert "market, currency, tick rule" in violation.message
