"""Strict schema for strategic and regional market-weight records."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omra.core import Dec

UnitWeight = Annotated[Dec, Field(ge=Decimal(0), le=Decimal(1))]
PercentagePoints = Annotated[Dec, Field(gt=Decimal(0), le=Decimal(100))]
TopLevelKey = Literal["equity", "bond", "alternative"]
EquityRegionKey = Literal["kr", "us", "dev_ex_us"]

_TOP_LEVEL_KEYS = frozenset({"equity", "bond", "alternative"})
_EQUITY_REGION_KEYS = frozenset({"kr", "us", "dev_ex_us"})


class EquityRegions(BaseModel):
    """Monthly MSCI regional inputs, nullable until the first measured load."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["msci_acwi_imi"]
    weights: Mapping[EquityRegionKey, UnitWeight | None]

    @field_validator("weights")
    @classmethod
    def _validate_weight_keys(
        cls,
        value: Mapping[EquityRegionKey, Decimal | None],
    ) -> Mapping[EquityRegionKey, Decimal | None]:
        actual = frozenset(value)
        if actual != _EQUITY_REGION_KEYS:
            missing = sorted(_EQUITY_REGION_KEYS - actual)
            extra = sorted(actual - _EQUITY_REGION_KEYS)
            raise ValueError(
                "equity region keys must exactly match "
                f"{sorted(_EQUITY_REGION_KEYS)} (missing={missing}, extra={extra})"
            )
        return value


class MarketWeightsFile(BaseModel):
    """Human-owned top-level weights plus measured regional weights."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    as_of: date
    top_level: Mapping[TopLevelKey, UnitWeight]
    equity_regions: EquityRegions
    region_shift_approve_pp: PercentagePoints = Decimal(5)

    @field_validator("top_level")
    @classmethod
    def _validate_top_level_keys(
        cls,
        value: Mapping[TopLevelKey, Decimal],
    ) -> Mapping[TopLevelKey, Decimal]:
        actual = frozenset(value)
        if actual != _TOP_LEVEL_KEYS:
            missing = sorted(_TOP_LEVEL_KEYS - actual)
            extra = sorted(actual - _TOP_LEVEL_KEYS)
            raise ValueError(
                "top-level keys must exactly match "
                f"{sorted(_TOP_LEVEL_KEYS)} (missing={missing}, extra={extra})"
            )
        return value


__all__ = ["EquityRegions", "MarketWeightsFile"]
