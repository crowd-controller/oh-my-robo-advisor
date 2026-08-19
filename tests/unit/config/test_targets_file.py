"""Unit contracts for the targets.yaml record schema."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError
from omra.config.files import RecordFile, TargetsFile


def _target_values() -> dict[str, object]:
    return {
        "version": 12,
        "as_of": date(2026, 8, 1),
        "risk_level": 6,
        "weights": {"KRX:360750": "0.62", "NASD:VTI": "0.37"},
        "cash": "0.01",
    }


def test_targets_fields_and_optional_inputs_hash_match_the_record_contract() -> None:
    targets = TargetsFile.model_validate(_target_values())

    assert targets.version == 12
    assert targets.as_of == date(2026, 8, 1)
    assert targets.risk_level == 6
    assert targets.weights == {
        "KRX:360750": Decimal("0.62"),
        "NASD:VTI": Decimal("0.37"),
    }
    assert targets.cash == Decimal("0.01")
    assert targets.inputs_hash is None

    with_hash = TargetsFile.model_validate(
        {**_target_values(), "inputs_hash": "sha256:policy-inputs"}
    )
    assert with_hash.inputs_hash == "sha256:policy-inputs"


@pytest.mark.parametrize("key", ["KRX:360750", "NASD:VTI", "UPBIT:KRW-BTC"])
def test_targets_reuses_exact_core_instrument_keys(key: str) -> None:
    values = _target_values()
    values["weights"] = {key: "0.99"}

    assert tuple(TargetsFile.model_validate(values).weights) == (key,)


@pytest.mark.parametrize(
    "key",
    ["KRX360750", "UNKNOWN:VTI", "KRX:", "krx:360750", "KRX:36 0750"],
)
def test_targets_rejects_every_malformed_instrument_key(key: str) -> None:
    values = _target_values()
    values["weights"] = {key: "0.99"}

    with pytest.raises(ValidationError, match="invalid instrument key") as raised:
        TargetsFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("weights",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", 0),
        ("risk_level", 0),
        ("risk_level", 11),
        ("cash", "-0.01"),
        ("cash", "1.01"),
    ],
)
def test_targets_rejects_out_of_range_scalar_values(field: str, value: object) -> None:
    values = _target_values()
    values[field] = value

    with pytest.raises(ValidationError):
        TargetsFile.model_validate(values)


@pytest.mark.parametrize("weight", ["-0.01", "1.01"])
def test_targets_rejects_out_of_range_weights(weight: str) -> None:
    values = _target_values()
    values["weights"] = {"KRX:360750": weight}

    with pytest.raises(ValidationError):
        TargetsFile.model_validate(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("weights", {"KRX:360750": 0.99}),
        ("cash", 0.01),
    ],
)
def test_targets_rejects_float_at_every_decimal_boundary(
    field: str,
    value: object,
) -> None:
    values = _target_values()
    values[field] = value

    with pytest.raises(ValidationError, match="float input is forbidden"):
        TargetsFile.model_validate(values)


def test_targets_rejects_unknown_fields_and_attribute_mutation() -> None:
    with pytest.raises(ValidationError) as extra_error:
        TargetsFile.model_validate({**_target_values(), "optimizer": "mvo"})
    assert extra_error.value.errors()[0]["loc"] == ("optimizer",)

    targets = TargetsFile.model_validate(_target_values())
    field_name = "risk_level"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(targets, field_name, 7)


def test_record_file_loads_targets_and_supports_cold_start_absence(tmp_path: Path) -> None:
    source = tmp_path / "targets.yaml"
    source.write_text(
        """version: 12
as_of: 2026-08-01
risk_level: 6
weights:
  "KRX:360750": "0.62"
  "NASD:VTI": "0.37"
cash: "0.01"
inputs_hash: "sha256:policy-inputs"
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, TargetsFile)

    assert loaded is not None
    assert loaded.model is TargetsFile
    assert loaded.data.weights["KRX:360750"] == Decimal("0.62")
    assert loaded.data.inputs_hash == "sha256:policy-inputs"
    assert RecordFile.load(tmp_path / "missing-targets.yaml", TargetsFile, required=False) is None


def test_record_file_reports_source_for_invalid_target_key(tmp_path: Path) -> None:
    source = tmp_path / "targets.yaml"
    source.write_text(
        """version: 1
as_of: 2026-08-01
risk_level: 6
weights:
  "krx:360750": "0.99"
cash: "0.01"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, TargetsFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "weights"
    assert "invalid instrument key" in violation.message
