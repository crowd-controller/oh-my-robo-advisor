"""Unit contracts for the goals.yaml record schema."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError
from omra.config.files import (
    GlidePathBand,
    GlidePathCfg,
    GoalsFile,
    RecordFile,
    WithdrawalCfg,
)


def _goals_values() -> dict[str, object]:
    return {
        "goals": [
            {
                "id": "retirement",
                "kind": "accumulate",
                "target_amount_krw": 1_500_000_000,
                "target_date": date(2050, 12, 31),
                "risk_level": 6,
            }
        ],
        "glide_path": {},
    }


def test_goals_file_uses_the_canonical_default_glide_path() -> None:
    goals = GoalsFile.model_validate(_goals_values())

    assert goals.goals[0].id == "retirement"
    assert goals.goals[0].kind == "accumulate"
    assert goals.goals[0].target_amount_krw == 1_500_000_000
    assert goals.goals[0].target_date == date(2050, 12, 31)
    assert goals.goals[0].risk_level == 6
    assert goals.glide_path.mode == "remaining_years_bands"
    assert tuple((band.min_years, band.rule) for band in goals.glide_path.bands) == (
        (15, "cap_at_level"),
        (5, "linear_down"),
        (0, "quarterly_step_down"),
    )
    assert goals.glide_path.floor_level == 3
    assert goals.glide_path.transition_months == 3
    assert goals.withdrawal is None


def test_withdrawal_defaults_are_four_percent_and_inflation_linked() -> None:
    withdrawal = WithdrawalCfg()

    assert withdrawal.initial_rate == Decimal("0.04")
    assert withdrawal.inflation_link is True

    values = _goals_values()
    values["withdrawal"] = {}
    goals = GoalsFile.model_validate(values)
    assert goals.withdrawal == withdrawal


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "Retirement"),
        ("id", "r"),
        ("kind", "spend"),
        ("target_amount_krw", 0),
        ("risk_level", 0),
        ("risk_level", 11),
    ],
)
def test_goal_identity_kind_amount_and_risk_are_strict(field: str, value: object) -> None:
    values = _goals_values()
    goal = dict(values["goals"][0])  # type: ignore[index]
    goal[field] = value
    values["goals"] = [goal]

    with pytest.raises(ValidationError):
        GoalsFile.model_validate(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", "calendar_year_bands"),
        ("floor_level", 0),
        ("floor_level", 11),
        ("transition_months", 0),
    ],
)
def test_glide_path_literals_and_bounds_are_strict(field: str, value: object) -> None:
    values = _goals_values()
    values["glide_path"] = {field: value}

    with pytest.raises(ValidationError):
        GoalsFile.model_validate(values)


def test_glide_band_rule_vocabulary_is_exact() -> None:
    with pytest.raises(ValidationError) as raised:
        GlidePathBand(min_years=5, rule="linear")  # type: ignore[arg-type]

    assert raised.value.errors()[0]["loc"] == ("rule",)


@pytest.mark.parametrize(
    "bands",
    [
        [],
        [
            {"min_years": 5, "rule": "linear_down"},
            {"min_years": 15, "rule": "cap_at_level"},
            {"min_years": 0, "rule": "quarterly_step_down"},
        ],
        [
            {"min_years": 15, "rule": "cap_at_level"},
            {"min_years": 15, "rule": "linear_down"},
            {"min_years": 0, "rule": "quarterly_step_down"},
        ],
        [
            {"min_years": 15, "rule": "cap_at_level"},
            {"min_years": 5, "rule": "linear_down"},
        ],
    ],
)
def test_glide_bands_are_descending_and_end_in_a_zero_year_catch_all(
    bands: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        GlidePathCfg(bands=bands)  # type: ignore[arg-type]


@pytest.mark.parametrize("initial_rate", [0.04, "0", "1.01"])
def test_withdrawal_rate_rejects_float_and_out_of_range_values(
    initial_rate: object,
) -> None:
    with pytest.raises(ValidationError):
        WithdrawalCfg(initial_rate=initial_rate)  # type: ignore[arg-type]


def test_goals_models_reject_unknown_fields_and_mutation() -> None:
    values = _goals_values()
    values["glide_path"] = {"rebalance": "monthly"}
    with pytest.raises(ValidationError) as extra_error:
        GoalsFile.model_validate(values)
    assert extra_error.value.errors()[0]["loc"] == ("glide_path", "rebalance")

    goals = GoalsFile.model_validate(_goals_values())
    field_name = "withdrawal"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(goals, field_name, WithdrawalCfg())
    band_field = "min_years"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(goals.glide_path.bands[0], band_field, 20)


def test_record_file_loads_goals_with_explicit_withdrawal(tmp_path: Path) -> None:
    source = tmp_path / "goals.yaml"
    source.write_text(
        """goals:
  - id: retirement
    kind: withdraw
    target_amount_krw: 1500000000
    target_date: 2050-12-31
    risk_level: 6
glide_path:
  mode: remaining_years_bands
  floor_level: 3
  transition_months: 3
withdrawal:
  initial_rate: "0.04"
  inflation_link: true
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, GoalsFile)

    assert loaded is not None
    assert loaded.data.goals[0].kind == "withdraw"
    assert loaded.data.glide_path.bands[1].rule == "linear_down"
    assert loaded.data.withdrawal is not None
    assert loaded.data.withdrawal.initial_rate == Decimal("0.04")


def test_record_file_reports_nested_goal_error_path_and_source(tmp_path: Path) -> None:
    source = tmp_path / "goals.yaml"
    source.write_text(
        """goals:
  - id: retirement
    kind: accumulate
    target_amount_krw: 1500000000
    target_date: 2050-12-31
    risk_level: 11
glide_path: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, GoalsFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "goals[0].risk_level"
