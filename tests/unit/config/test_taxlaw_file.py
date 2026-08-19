"""Unit contracts for tax-law records and effective-date selection."""

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError, EffectiveVersionMissing, VersionedFile
from omra.config.files import RecordFile, TaxLawFile, TaxParams, TaxVersion

_ROOT = Path(__file__).resolve().parents[3]
_SEED = _ROOT / "config" / "tax.yaml"
_DECIMAL_FIELDS = (
    "overseas_cg_rate",
    "overseas_cg_deduction_krw",
    "dividend_wht_rate",
    "fin_income_aggregate_threshold_krw",
    "isa_free_limit_krw",
    "isa_excess_rate",
    "isa_annual_contrib_cap_krw",
    "pension_deduct_cap_savings_krw",
    "pension_deduct_cap_total_krw",
    "pension_contrib_cap_total_krw",
    "harvest_cost_gate_factor",
    "harvest_annual_nav_cap",
)
_LAW_FIELDS = (*_DECIMAL_FIELDS, "crypto_tax_enabled")
_OPERATING_FIELDS = frozenset(
    {
        "harvest_start",
        "deduction",
        "income_alerts",
        "basis_price_source",
        "isa_free_limit",
        "isa_usage_alert",
        "isa_contract_start_date",
        "isa_usage_opening_amount",
        "isa_usage_opening_as_of",
        "harvest_rebuy_buffer_pct",
        "health_insurance_status",
        "user_marginal_credit_rate",
        "harvest_auto_enabled",
        "fill_pension_to_limit",
        "gap_check_date",
        "reminders",
        "transfer_reserve_expiry_days",
    }
)


def _params_values() -> dict[str, object]:
    return {
        "overseas_cg_rate": "0.22",
        "overseas_cg_deduction_krw": "2500000",
        "dividend_wht_rate": "0.154",
        "fin_income_aggregate_threshold_krw": "20000000",
        "isa_free_limit_krw": "2000000",
        "isa_excess_rate": "0.099",
        "isa_annual_contrib_cap_krw": "20000000",
        "pension_deduct_cap_savings_krw": "6000000",
        "pension_deduct_cap_total_krw": "9000000",
        "pension_contrib_cap_total_krw": "18000000",
        "harvest_cost_gate_factor": "0.5",
        "harvest_annual_nav_cap": "0.20",
        "crypto_tax_enabled": False,
    }


def _version_values(
    effective_from: date = date(2026, 1, 1),
    *,
    note: str = "canonical",
) -> dict[str, object]:
    return {
        "effective_from": effective_from,
        "note": note,
        "params": _params_values(),
    }


def _file_values(*versions: dict[str, object]) -> dict[str, object]:
    rows = versions or (_version_values(),)
    return {"schema_version": 1, "versions": list(rows)}


def _params(row: dict[str, object]) -> dict[str, object]:
    values = row["params"]
    assert isinstance(values, dict)
    return values


def test_seed_loads_every_canonical_2026_tax_law_value_exactly() -> None:
    loaded = RecordFile.load(_SEED, TaxLawFile)

    assert loaded is not None
    assert loaded.model is TaxLawFile
    assert loaded.data.schema_version == 1
    assert len(loaded.data.versions) == 1
    version = loaded.data.versions[0]
    assert version.effective_from == date(2026, 1, 1)
    assert version.note == "2026 세제 기준"
    params = version.params
    assert params.effective_from == version.effective_from
    assert {field: getattr(params, field) for field in _DECIMAL_FIELDS} == {
        "overseas_cg_rate": Decimal("0.22"),
        "overseas_cg_deduction_krw": Decimal("2500000"),
        "dividend_wht_rate": Decimal("0.154"),
        "fin_income_aggregate_threshold_krw": Decimal("20000000"),
        "isa_free_limit_krw": Decimal("2000000"),
        "isa_excess_rate": Decimal("0.099"),
        "isa_annual_contrib_cap_krw": Decimal("20000000"),
        "pension_deduct_cap_savings_krw": Decimal("6000000"),
        "pension_deduct_cap_total_krw": Decimal("9000000"),
        "pension_contrib_cap_total_krw": Decimal("18000000"),
        "harvest_cost_gate_factor": Decimal("0.5"),
        "harvest_annual_nav_cap": Decimal("0.20"),
    }
    assert params.crypto_tax_enabled is False
    assert len(_LAW_FIELDS) == 13


def test_tax_params_fields_are_law_only_and_match_the_consumer_contract() -> None:
    assert tuple(TaxParams.model_fields) == (
        "effective_from",
        "overseas_cg_rate",
        "overseas_cg_deduction_krw",
        "dividend_wht_rate",
        "fin_income_aggregate_threshold_krw",
        "isa_free_limit_krw",
        "isa_excess_rate",
        "isa_annual_contrib_cap_krw",
        "pension_deduct_cap_savings_krw",
        "pension_deduct_cap_total_krw",
        "pension_contrib_cap_total_krw",
        "harvest_cost_gate_factor",
        "harvest_annual_nav_cap",
        "crypto_tax_enabled",
    )
    assert _OPERATING_FIELDS.isdisjoint(TaxParams.model_fields)
    assert tuple(TaxVersion.model_fields) == ("effective_from", "note", "params")
    assert tuple(TaxLawFile.model_fields) == ("schema_version", "versions")


def test_tax_params_defaults_are_the_canonical_law_values() -> None:
    params = TaxParams(effective_from=date(2026, 1, 1))

    assert params.overseas_cg_rate == Decimal("0.22")
    assert params.overseas_cg_deduction_krw == Decimal("2500000")
    assert params.dividend_wht_rate == Decimal("0.154")
    assert params.fin_income_aggregate_threshold_krw == Decimal("20000000")
    assert params.isa_free_limit_krw == Decimal("2000000")
    assert params.isa_excess_rate == Decimal("0.099")
    assert params.isa_annual_contrib_cap_krw == Decimal("20000000")
    assert params.pension_deduct_cap_savings_krw == Decimal("6000000")
    assert params.pension_deduct_cap_total_krw == Decimal("9000000")
    assert params.pension_contrib_cap_total_krw == Decimal("18000000")
    assert params.harvest_cost_gate_factor == Decimal("0.5")
    assert params.harvest_annual_nav_cap == Decimal("0.20")
    assert params.crypto_tax_enabled is False


def test_version_row_is_the_single_physical_effective_date_source() -> None:
    row = _version_values(date(2027, 7, 1))
    law = TaxLawFile.model_validate(_file_values(row))

    assert law.versions[0].effective_from == date(2027, 7, 1)
    assert law.versions[0].params.effective_from == date(2027, 7, 1)

    _params(row)["effective_from"] = date(2020, 1, 1)
    with pytest.raises(ValidationError, match="derived from the version row") as raised:
        TaxLawFile.model_validate(_file_values(row))
    assert raised.value.errors()[0]["loc"] == ("versions", 0, "params")


def test_versions_are_normalized_newest_first_without_changing_payloads() -> None:
    law = TaxLawFile.model_validate(
        _file_values(
            _version_values(date(2025, 1, 1), note="old"),
            _version_values(date(2027, 1, 1), note="new"),
            _version_values(date(2026, 6, 1), note="middle"),
        )
    )

    assert tuple(version.effective_from for version in law.versions) == (
        date(2027, 1, 1),
        date(2026, 6, 1),
        date(2025, 1, 1),
    )
    assert tuple(version.note for version in law.versions) == ("new", "middle", "old")
    assert all(version.params.effective_from == version.effective_from for version in law.versions)


def test_empty_and_duplicate_tax_versions_are_rejected() -> None:
    with pytest.raises(ValidationError) as empty:
        TaxLawFile.model_validate({"schema_version": 1, "versions": []})
    assert empty.value.errors()[0]["loc"] == ("versions",)

    duplicate_day = date(2026, 1, 1)
    with pytest.raises(ValidationError, match="must be unique") as duplicate:
        TaxLawFile.model_validate(
            _file_values(
                _version_values(duplicate_day, note="first"),
                _version_values(duplicate_day, note="second"),
            )
        )
    assert duplicate.value.errors()[0]["loc"] == ("versions",)


def test_schema_version_must_be_positive() -> None:
    values = _file_values()
    values["schema_version"] = 0

    with pytest.raises(ValidationError) as raised:
        TaxLawFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("schema_version",)


@pytest.mark.parametrize("field", _DECIMAL_FIELDS)
def test_every_tax_decimal_rejects_float_input(field: str) -> None:
    row = _version_values()
    _params(row)[field] = 0.5

    with pytest.raises(ValidationError, match="float input is forbidden") as raised:
        TaxLawFile.model_validate(_file_values(row))

    assert raised.value.errors()[0]["loc"] == ("versions", 0, "params", field)


def test_models_forbid_unknown_fields_at_every_record_level() -> None:
    root = _file_values()
    root["jurisdiction"] = "KR"
    with pytest.raises(ValidationError) as root_error:
        TaxLawFile.model_validate(root)
    assert root_error.value.errors()[0]["loc"] == ("jurisdiction",)

    row = _version_values()
    row["approved_by"] = "operator"
    with pytest.raises(ValidationError) as row_error:
        TaxLawFile.model_validate(_file_values(row))
    assert row_error.value.errors()[0]["loc"] == ("versions", 0, "approved_by")

    row = _version_values()
    _params(row)["harvest_start"] = "11-25"
    with pytest.raises(ValidationError) as params_error:
        TaxLawFile.model_validate(_file_values(row))
    assert params_error.value.errors()[0]["loc"] == (
        "versions",
        0,
        "params",
        "harvest_start",
    )


def test_tax_models_and_generic_version_container_are_frozen() -> None:
    law = TaxLawFile.model_validate(_file_values())
    version = law.versions[0]
    params = version.params

    params_field = "crypto_tax_enabled"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(params, params_field, True)
    version_field = "note"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(version, version_field, "changed")
    file_field = "schema_version"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(law, file_field, 2)

    versioned = law.to_versioned()
    versioned_field = "versions"
    with pytest.raises(FrozenInstanceError):
        setattr(versioned, versioned_field, ())


def test_versioned_file_normalizes_and_selects_boundaries_without_lookahead() -> None:
    versions = VersionedFile(
        (
            (date(2026, 7, 1), "second"),
            (date(2025, 1, 1), "first"),
            (date(2027, 1, 1), "third"),
        )
    )

    assert versions.versions == (
        (date(2027, 1, 1), "third"),
        (date(2026, 7, 1), "second"),
        (date(2025, 1, 1), "first"),
    )
    assert versions.at_or_none(date(2024, 12, 31)) is None
    assert versions.at(date(2025, 1, 1)) == "first"
    assert versions.at(date(2026, 6, 30)) == "first"
    assert versions.at(date(2026, 7, 1)) == "second"
    assert versions.at(date(2026, 12, 31)) == "second"
    assert versions.at(date(2027, 1, 1)) == "third"
    assert versions.latest() == "third"


def test_versioned_file_reports_all_available_dates_when_none_is_effective() -> None:
    versions = VersionedFile(
        (
            (date(2027, 1, 1), "new"),
            (date(2026, 1, 1), "old"),
        )
    )

    with pytest.raises(EffectiveVersionMissing) as raised:
        versions.at(date(2025, 12, 31))

    assert raised.value.kst_date == date(2025, 12, 31)
    assert raised.value.available_from == (date(2026, 1, 1), date(2027, 1, 1))
    assert raised.value.code == "config.effective_version_missing"
    assert "2025-12-31" in str(raised.value)
    assert "2026-01-01, 2027-01-01" in str(raised.value)


def test_versioned_file_rejects_empty_and_duplicate_dates() -> None:
    with pytest.raises(ValueError, match="at least one version"):
        VersionedFile[object](())

    duplicate = date(2026, 1, 1)
    with pytest.raises(ValueError, match="must be unique"):
        VersionedFile(((duplicate, "first"), (duplicate, "second")))


def test_versioned_file_at_does_not_confuse_a_none_value_with_a_missing_version() -> None:
    versions = VersionedFile(((date(2026, 1, 1), None),))

    assert versions.at(date(2026, 1, 1)) is None


def test_tax_law_converts_to_versioned_values_without_copying_params() -> None:
    law = TaxLawFile.model_validate(
        _file_values(
            _version_values(date(2025, 1, 1), note="old"),
            _version_values(date(2026, 1, 1), note="new"),
        )
    )

    versioned = law.to_versioned()

    assert versioned.latest() is law.versions[0].params
    assert versioned.at(date(2025, 12, 31)) is law.versions[1].params
    assert versioned.at(date(2026, 1, 1)) is law.versions[0].params


def test_record_file_reports_nested_decimal_path_and_source(tmp_path: Path) -> None:
    source = tmp_path / "tax.yaml"
    source.write_text(
        _SEED.read_text(encoding="utf-8").replace(
            'overseas_cg_rate: "0.22"',
            "overseas_cg_rate: 0.22",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, TaxLawFile)

    assert raised.value.violations[0].path == "versions[0].params.overseas_cg_rate"
    assert raised.value.violations[0].source == source
    assert "float input is forbidden" in raised.value.violations[0].message
