"""Unit contracts for the external_income.yaml record schema."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError
from omra.config.files import ExternalIncome, ExternalIncomeFile, RecordFile


def _income_values() -> dict[str, object]:
    return {
        "id": "bank_deposit_1",
        "kind": "deposit",
        "principal_krw": 50_000_000,
        "annual_rate": "0.035",
        "maturity": date(2027, 3, 31),
        "payout": "at_maturity",
    }


def test_external_income_fields_match_the_canonical_record() -> None:
    income = ExternalIncome.model_validate(_income_values())

    assert income.id == "bank_deposit_1"
    assert income.kind == "deposit"
    assert income.principal_krw == 50_000_000
    assert income.annual_rate == Decimal("0.035")
    assert income.maturity == date(2027, 3, 31)
    assert income.payout == "at_maturity"


@pytest.mark.parametrize("kind", ["deposit", "bond", "other"])
@pytest.mark.parametrize("payout", ["monthly", "quarterly", "annual", "at_maturity"])
def test_income_kind_and_payout_vocabularies_accept_every_canonical_pair(
    kind: str,
    payout: str,
) -> None:
    values = _income_values()
    values["kind"] = kind
    values["payout"] = payout

    income = ExternalIncome.model_validate(values)
    assert income.kind == kind
    assert income.payout == payout


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "savings"),
        ("kind", "DEPOSIT"),
        ("payout", "semiannual"),
        ("payout", "maturity"),
        ("principal_krw", 0),
        ("principal_krw", -1),
        ("annual_rate", "-0.001"),
    ],
)
def test_income_vocabulary_principal_and_rate_bounds_are_strict(
    field: str,
    value: object,
) -> None:
    values = _income_values()
    values[field] = value

    with pytest.raises(ValidationError):
        ExternalIncome.model_validate(values)


def test_external_income_rejects_float_annual_rate() -> None:
    values = _income_values()
    values["annual_rate"] = 0.035

    with pytest.raises(ValidationError, match="float input is forbidden") as raised:
        ExternalIncome.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("annual_rate",)


def test_zero_annual_rate_is_valid() -> None:
    values = _income_values()
    values["annual_rate"] = "0"

    assert ExternalIncome.model_validate(values).annual_rate == Decimal(0)


def test_income_row_and_root_wrapper_are_frozen_and_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError) as extra_error:
        ExternalIncome.model_validate({**_income_values(), "institution": "private"})
    assert extra_error.value.errors()[0]["loc"] == ("institution",)

    row = ExternalIncome.model_validate(_income_values())
    income_file = ExternalIncomeFile((row,))
    row_field = "principal_krw"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(row, row_field, 1)
    root_field = "root"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(income_file, root_field, ())


def test_record_file_loads_canonical_income_root_sequence(tmp_path: Path) -> None:
    source = tmp_path / "external_income.yaml"
    source.write_text(
        """- id: bank_deposit_1
  kind: deposit
  principal_krw: 50000000
  annual_rate: "0.035"
  maturity: 2027-03-31
  payout: at_maturity
- id: treasury_bond_1
  kind: bond
  principal_krw: 10000000
  annual_rate: "0.04"
  maturity: 2028-06-30
  payout: quarterly
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, ExternalIncomeFile)

    assert loaded is not None
    assert loaded.model is ExternalIncomeFile
    assert len(loaded.data.root) == 2
    assert loaded.data.root[0].annual_rate == Decimal("0.035")
    assert loaded.data.root[1].payout == "quarterly"


def test_income_error_reports_second_row_decimal_path_and_source(tmp_path: Path) -> None:
    source = tmp_path / "external_income.yaml"
    source.write_text(
        """- id: bank_deposit_1
  kind: deposit
  principal_krw: 50000000
  annual_rate: "0.035"
  maturity: 2027-03-31
  payout: at_maturity
- id: treasury_bond_1
  kind: bond
  principal_krw: 10000000
  annual_rate: 0.04
  maturity: 2028-06-30
  payout: quarterly
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, ExternalIncomeFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "[1].annual_rate"
    assert "float input is forbidden" in violation.message
