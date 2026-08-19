"""Unit contracts for the market_weights.yaml record schema."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError
from omra.config.files import MarketWeightsFile, RecordFile


def _market_weight_values() -> dict[str, object]:
    return {
        "version": 4,
        "as_of": date(2026, 7, 31),
        "top_level": {
            "equity": "0.45",
            "bond": "0.45",
            "alternative": "0.10",
        },
        "equity_regions": {
            "source": "msci_acwi_imi",
            "weights": {
                "kr": None,
                "us": None,
                "dev_ex_us": None,
            },
        },
    }


def test_market_weights_preserves_nullable_regions_and_threshold_default() -> None:
    weights = MarketWeightsFile.model_validate(_market_weight_values())

    assert weights.version == 4
    assert weights.as_of == date(2026, 7, 31)
    assert weights.top_level == {
        "equity": Decimal("0.45"),
        "bond": Decimal("0.45"),
        "alternative": Decimal("0.10"),
    }
    assert weights.equity_regions.source == "msci_acwi_imi"
    assert weights.equity_regions.weights == {
        "kr": None,
        "us": None,
        "dev_ex_us": None,
    }
    assert weights.region_shift_approve_pp == Decimal(5)


@pytest.mark.parametrize(
    "top_level",
    [
        {"equity": "0.45", "bond": "0.45"},
        {
            "equity": "0.45",
            "bond": "0.45",
            "alternative": "0.10",
            "cash": "0",
        },
    ],
)
def test_top_level_key_set_must_be_exact(top_level: dict[str, object]) -> None:
    values = _market_weight_values()
    values["top_level"] = top_level

    with pytest.raises(ValidationError):
        MarketWeightsFile.model_validate(values)


@pytest.mark.parametrize(
    "regions",
    [
        {"kr": None, "us": None},
        {"kr": None, "us": None, "dev_ex_us": None, "em": None},
    ],
)
def test_equity_region_key_set_must_be_exact(regions: dict[str, object]) -> None:
    values = _market_weight_values()
    values["equity_regions"] = {
        "source": "msci_acwi_imi",
        "weights": regions,
    }

    with pytest.raises(ValidationError):
        MarketWeightsFile.model_validate(values)


def test_equity_region_source_vocabulary_is_exact() -> None:
    values = _market_weight_values()
    values["equity_regions"] = {
        "source": "msci_acwi",
        "weights": {"kr": None, "us": None, "dev_ex_us": None},
    }

    with pytest.raises(ValidationError) as raised:
        MarketWeightsFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("equity_regions", "source")


@pytest.mark.parametrize(
    ("path", "mutator"),
    [
        (
            "top_level.equity",
            lambda values: values["top_level"].__setitem__("equity", 0.45),
        ),
        (
            "equity_regions.weights.us",
            lambda values: values["equity_regions"]["weights"].__setitem__("us", 0.60),
        ),
        (
            "region_shift_approve_pp",
            lambda values: values.__setitem__("region_shift_approve_pp", 5.0),
        ),
    ],
)
def test_market_weights_rejects_float_at_every_decimal_boundary(
    path: str,
    mutator: object,
) -> None:
    values = _market_weight_values()
    mutator(values)  # type: ignore[operator]

    with pytest.raises(ValidationError, match="float input is forbidden") as raised:
        MarketWeightsFile.model_validate(values)

    rendered_locations = {
        ".".join(str(part) for part in item["loc"]) for item in raised.value.errors()
    }
    assert path in rendered_locations


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", 0),
        ("region_shift_approve_pp", "0"),
        ("region_shift_approve_pp", "101"),
    ],
)
def test_market_weight_scalar_bounds_are_strict(field: str, value: object) -> None:
    values = _market_weight_values()
    values[field] = value

    with pytest.raises(ValidationError):
        MarketWeightsFile.model_validate(values)


def test_market_weights_rejects_unknown_auto_update_and_mutation() -> None:
    with pytest.raises(ValidationError) as extra_error:
        MarketWeightsFile.model_validate({**_market_weight_values(), "auto_update": True})
    assert extra_error.value.errors()[0]["loc"] == ("auto_update",)

    weights = MarketWeightsFile.model_validate(_market_weight_values())
    field_name = "as_of"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(weights, field_name, date(2026, 8, 31))
    source_field = "source"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(weights.equity_regions, source_field, "other")


def test_record_file_loads_market_weights_with_unmeasured_regions(tmp_path: Path) -> None:
    source = tmp_path / "market_weights.yaml"
    source.write_text(
        """version: 4
as_of: 2026-07-31
top_level:
  equity: "0.45"
  bond: "0.45"
  alternative: "0.10"
equity_regions:
  source: msci_acwi_imi
  weights:
    kr: null
    us: null
    dev_ex_us: null
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, MarketWeightsFile)

    assert loaded is not None
    assert loaded.data.top_level["equity"] == Decimal("0.45")
    assert loaded.data.equity_regions.weights["dev_ex_us"] is None
    assert loaded.data.region_shift_approve_pp == Decimal(5)


def test_record_file_reports_nested_decimal_error_path_and_source(tmp_path: Path) -> None:
    source = tmp_path / "market_weights.yaml"
    source.write_text(
        """version: 4
as_of: 2026-07-31
top_level:
  equity: 0.45
  bond: "0.45"
  alternative: "0.10"
equity_regions:
  source: msci_acwi_imi
  weights:
    kr: null
    us: null
    dev_ex_us: null
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, MarketWeightsFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "top_level.equity"
    assert "float input is forbidden" in violation.message
