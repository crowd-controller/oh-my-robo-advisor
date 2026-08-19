"""Strict schema for independently loaded target-weight records."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omra.core import Dec, DomainError, parse_instrument_key

UnitWeight = Annotated[Dec, Field(ge=Decimal(0), le=Decimal(1))]


class TargetsFile(BaseModel):
    """A seed or generated total-portfolio target allocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    as_of: date
    risk_level: int = Field(ge=1, le=10)
    weights: Mapping[str, UnitWeight]
    cash: UnitWeight
    inputs_hash: str | None = None

    @field_validator("weights")
    @classmethod
    def _validate_instrument_keys(
        cls,
        value: Mapping[str, Decimal],
    ) -> Mapping[str, Decimal]:
        for key in value:
            try:
                parse_instrument_key(key)
            except DomainError as error:
                raise ValueError(f"invalid instrument key {key!r}: {error}") from error
        return value


__all__ = ["TargetsFile"]
