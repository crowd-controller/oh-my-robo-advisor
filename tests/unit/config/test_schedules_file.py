"""Unit contracts for the external_schedules.yaml record schema."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigSyntaxError, ConfigValidationError
from omra.config.files import ExternalSchedule, ExternalSchedulesFile, RecordFile


def _cash_schedule_values() -> dict[str, object]:
    return {
        "id": "pension_monthly_transfer",
        "account_id": "pension_savings",
        "kind": "cash_in",
        "instrument_key": None,
        "day_of_month": 25,
        "holiday_shift": "next_business_day",
        "amount_krw": 500_000,
        "amount_tolerance_krw": 1_000,
        "start_date": date(2026, 9, 1),
        "end_date": None,
    }


def _scheduled_fill_values() -> dict[str, object]:
    values = _cash_schedule_values()
    values.update(
        {
            "id": "general_vti_monthly",
            "account_id": "general",
            "kind": "scheduled_fill",
            "instrument_key": "NASD:VTI",
        }
    )
    return values


def test_external_schedule_fields_match_the_canonical_cash_in_record() -> None:
    schedule = ExternalSchedule.model_validate(_cash_schedule_values())

    assert schedule.id == "pension_monthly_transfer"
    assert schedule.account_id == "pension_savings"
    assert schedule.kind == "cash_in"
    assert schedule.instrument_key is None
    assert schedule.day_of_month == 25
    assert schedule.holiday_shift == "next_business_day"
    assert schedule.amount_krw == 500_000
    assert schedule.amount_tolerance_krw == 1_000
    assert schedule.start_date == date(2026, 9, 1)
    assert schedule.end_date is None


@pytest.mark.parametrize("day", [1, 28, 29, 30, 31])
def test_day_of_month_including_short_month_days_is_accepted(day: int) -> None:
    values = _cash_schedule_values()
    values["day_of_month"] = day

    assert ExternalSchedule.model_validate(values).day_of_month == day


@pytest.mark.parametrize("day", [0, 32])
def test_day_of_month_outside_calendar_bounds_is_rejected(day: int) -> None:
    values = _cash_schedule_values()
    values["day_of_month"] = day

    with pytest.raises(ValidationError):
        ExternalSchedule.model_validate(values)


@pytest.mark.parametrize("kind", ["cash_out", "fill", "SCHEDULED_FILL"])
def test_schedule_kind_vocabulary_is_exact(kind: str) -> None:
    values = _cash_schedule_values()
    values["kind"] = kind

    with pytest.raises(ValidationError) as raised:
        ExternalSchedule.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("kind",)


@pytest.mark.parametrize(
    "holiday_shift",
    ["following", "previous_business_day", "none"],
)
def test_holiday_shift_vocabulary_is_exact(holiday_shift: str) -> None:
    values = _cash_schedule_values()
    values["holiday_shift"] = holiday_shift

    with pytest.raises(ValidationError) as raised:
        ExternalSchedule.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("holiday_shift",)


@pytest.mark.parametrize(
    ("values", "match"),
    [
        (_scheduled_fill_values() | {"instrument_key": None}, "requires instrument_key"),
        (_scheduled_fill_values() | {"instrument_key": "nasd:VTI"}, "invalid instrument key"),
        (_cash_schedule_values() | {"instrument_key": "KRX:360750"}, "must not declare"),
    ],
)
def test_instrument_key_presence_and_exact_match_follow_schedule_kind(
    values: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match) as raised:
        ExternalSchedule.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("instrument_key",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "Invalid-Id"),
        ("id", "x"),
        ("amount_krw", 0),
        ("amount_tolerance_krw", 0),
    ],
)
def test_schedule_identifier_and_positive_amounts_are_strict(
    field: str,
    value: object,
) -> None:
    values = _cash_schedule_values()
    values[field] = value

    with pytest.raises(ValidationError):
        ExternalSchedule.model_validate(values)


def test_schedule_identifier_allows_at_most_sixty_four_characters() -> None:
    values = _cash_schedule_values()
    values["id"] = "a" + ("b" * 63)
    assert len(ExternalSchedule.model_validate(values).id) == 64

    values["id"] = "a" + ("b" * 64)
    with pytest.raises(ValidationError):
        ExternalSchedule.model_validate(values)


@pytest.mark.parametrize("end_date", [date(2026, 9, 1), date(2026, 8, 31)])
def test_end_date_must_be_later_than_start_date(end_date: date) -> None:
    values = _cash_schedule_values()
    values["end_date"] = end_date

    with pytest.raises(ValidationError, match="later than start_date") as raised:
        ExternalSchedule.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("end_date",)


def test_end_date_after_start_date_is_accepted() -> None:
    values = _cash_schedule_values()
    values["end_date"] = date(2026, 9, 2)

    assert ExternalSchedule.model_validate(values).end_date == date(2026, 9, 2)


def test_schedule_row_and_root_wrapper_are_frozen_and_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError) as extra_error:
        ExternalSchedule.model_validate({**_cash_schedule_values(), "timezone": "Asia/Seoul"})
    assert extra_error.value.errors()[0]["loc"] == ("timezone",)

    row = ExternalSchedule.model_validate(_cash_schedule_values())
    schedules = ExternalSchedulesFile((row,))
    row_field = "amount_krw"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(row, row_field, 600_000)
    root_field = "root"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(schedules, root_field, ())


def test_record_file_loads_canonical_schedule_root_sequence(tmp_path: Path) -> None:
    source = tmp_path / "external_schedules.yaml"
    source.write_text(
        """- id: pension_monthly_transfer
  account_id: pension_savings
  kind: cash_in
  instrument_key: null
  day_of_month: 31
  holiday_shift: next_business_day
  amount_krw: 500000
  amount_tolerance_krw: 1000
  start_date: 2026-09-01
  end_date: null
- id: general_vti_monthly
  account_id: general
  kind: scheduled_fill
  instrument_key: "NASD:VTI"
  day_of_month: 25
  holiday_shift: prev_business_day
  amount_krw: 300000
  amount_tolerance_krw: 2000
  start_date: 2026-09-01
  end_date: 2027-09-01
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, ExternalSchedulesFile)

    assert loaded is not None
    assert loaded.model is ExternalSchedulesFile
    assert len(loaded.data.root) == 2
    assert loaded.data.root[0].day_of_month == 31
    assert loaded.data.root[1].instrument_key == "NASD:VTI"


def test_schedule_sequence_reuses_duplicate_key_rejection(tmp_path: Path) -> None:
    source = tmp_path / "external_schedules.yaml"
    source.write_text(
        """- id: pension_monthly_transfer
  account_id: pension_savings
  kind: cash_in
  day_of_month: 25
  holiday_shift: skip
  amount_krw: 500000
  amount_krw: 600000
  amount_tolerance_krw: 1000
  start_date: 2026-09-01
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigSyntaxError, match="duplicate key 'amount_krw'"):
        RecordFile.load(source, ExternalSchedulesFile)


def test_schedule_error_reports_second_row_field_and_source(tmp_path: Path) -> None:
    source = tmp_path / "external_schedules.yaml"
    source.write_text(
        """- id: pension_monthly_transfer
  account_id: pension_savings
  kind: cash_in
  day_of_month: 25
  holiday_shift: skip
  amount_krw: 500000
  amount_tolerance_krw: 1000
  start_date: 2026-09-01
- id: general_vti_monthly
  account_id: general
  kind: scheduled_fill
  instrument_key: "NASD:VTI"
  day_of_month: 25
  holiday_shift: skip
  amount_krw: 300000
  amount_tolerance_krw: 0
  start_date: 2026-09-01
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, ExternalSchedulesFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "[1].amount_tolerance_krw"


def test_schedule_root_model_rejects_mapping_document_at_root(tmp_path: Path) -> None:
    source = tmp_path / "external_schedules.yaml"
    source.write_text("id: not-a-sequence\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, ExternalSchedulesFile)

    assert raised.value.violations[0].path == "$"
