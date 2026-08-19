"""Strict schema for external cash-in and broker-scheduled expectations."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationInfo, field_validator

from omra.core import DomainError, parse_instrument_key


class ExternalSchedule(BaseModel):
    """One human-declared recurring external cash or scheduled-fill expectation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    account_id: str
    kind: Literal["cash_in", "scheduled_fill"]
    instrument_key: str | None = Field(default=None, validate_default=True)
    day_of_month: int = Field(ge=1, le=31)
    holiday_shift: Literal["next_business_day", "prev_business_day", "skip"]
    amount_krw: int = Field(gt=0)
    amount_tolerance_krw: int = Field(gt=0)
    start_date: date
    end_date: date | None = Field(default=None, validate_default=True)

    @field_validator("instrument_key")
    @classmethod
    def _validate_instrument_key(
        cls,
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        kind = info.data.get("kind")
        if kind == "cash_in":
            if value is not None:
                raise ValueError("cash_in schedule must not declare instrument_key")
            return None
        if kind == "scheduled_fill":
            if value is None:
                raise ValueError("scheduled_fill schedule requires instrument_key")
            try:
                parse_instrument_key(value)
            except DomainError as error:
                raise ValueError(f"invalid instrument key {value!r}: {error}") from error
        return value

    @field_validator("end_date")
    @classmethod
    def _validate_end_date(
        cls,
        value: date | None,
        info: ValidationInfo,
    ) -> date | None:
        start_date = info.data.get("start_date")
        if value is not None and isinstance(start_date, date) and value <= start_date:
            raise ValueError("end_date must be later than start_date")
        return value


class ExternalSchedulesFile(RootModel[tuple[ExternalSchedule, ...]]):
    """The canonical sequence-root external_schedules.yaml document."""

    model_config = ConfigDict(frozen=True)


__all__ = ["ExternalSchedule", "ExternalSchedulesFile"]
