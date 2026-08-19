"""Strict schema for externally held financial-income records."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from omra.core import Dec

NonNegativeRate = Annotated[Dec, Field(ge=Decimal(0))]


class ExternalIncome(BaseModel):
    """One externally held deposit, bond, or other income-bearing asset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Literal["deposit", "bond", "other"]
    principal_krw: int = Field(gt=0)
    annual_rate: NonNegativeRate
    maturity: date
    payout: Literal["monthly", "quarterly", "annual", "at_maturity"]


class ExternalIncomeFile(RootModel[tuple[ExternalIncome, ...]]):
    """The canonical sequence-root external_income.yaml document."""

    model_config = ConfigDict(frozen=True)


__all__ = ["ExternalIncome", "ExternalIncomeFile"]
