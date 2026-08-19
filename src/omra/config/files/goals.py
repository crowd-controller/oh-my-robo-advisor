"""Strict schema for human-controlled financial goals and glide paths."""

from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omra.core import Dec

Rate = Annotated[Dec, Field(gt=Decimal(0), le=Decimal(1))]


class Goal(BaseModel):
    """One human-defined accumulation or withdrawal objective."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    kind: Literal["accumulate", "withdraw"]
    target_amount_krw: int = Field(gt=0)
    target_date: date
    risk_level: int = Field(ge=1, le=10)


class GlidePathBand(BaseModel):
    """One remaining-years threshold and its canonical glide rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_years: int = Field(ge=0)
    rule: Literal["cap_at_level", "linear_down", "quarterly_step_down"]


def _default_glide_bands() -> tuple[GlidePathBand, ...]:
    return (
        GlidePathBand(min_years=15, rule="cap_at_level"),
        GlidePathBand(min_years=5, rule="linear_down"),
        GlidePathBand(min_years=0, rule="quarterly_step_down"),
    )


class GlidePathCfg(BaseModel):
    """Human-controlled remaining-years band configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["remaining_years_bands"] = "remaining_years_bands"
    bands: tuple[GlidePathBand, ...] = Field(default_factory=_default_glide_bands)
    floor_level: int = Field(default=3, ge=1, le=10)
    transition_months: int = Field(default=3, ge=1)

    @field_validator("bands")
    @classmethod
    def _validate_band_boundaries(
        cls,
        value: tuple[GlidePathBand, ...],
    ) -> tuple[GlidePathBand, ...]:
        if not value:
            raise ValueError("glide path must contain at least one band")
        boundaries = tuple(band.min_years for band in value)
        if any(upper <= lower for upper, lower in pairwise(boundaries)):
            raise ValueError("glide path min_years must be strictly descending")
        if boundaries[-1] != 0:
            raise ValueError("glide path must end with a zero-year catch-all band")
        return value


class WithdrawalCfg(BaseModel):
    """Initial withdrawal policy values owned by goals.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_rate: Rate = Decimal("0.04")
    inflation_link: bool = True


class GoalsFile(BaseModel):
    """Human-controlled goals and their shared glide-path policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    goals: tuple[Goal, ...]
    glide_path: GlidePathCfg
    withdrawal: WithdrawalCfg | None = None


__all__ = [
    "GlidePathBand",
    "GlidePathCfg",
    "Goal",
    "GoalsFile",
    "WithdrawalCfg",
]
