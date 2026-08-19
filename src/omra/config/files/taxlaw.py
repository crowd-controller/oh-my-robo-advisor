"""Strict effective-date schema for human-approved tax-law parameters."""

from collections import Counter
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from omra.config.versioned import VersionedFile
from omra.core import Dec


class TaxParams(BaseModel):
    """Tax-law values only; operational switches remain in ``AppConfig``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_from: date
    overseas_cg_rate: Dec = Decimal("0.22")
    overseas_cg_deduction_krw: Dec = Decimal("2500000")
    dividend_wht_rate: Dec = Decimal("0.154")
    fin_income_aggregate_threshold_krw: Dec = Decimal("20000000")
    isa_free_limit_krw: Dec = Decimal("2000000")
    isa_excess_rate: Dec = Decimal("0.099")
    isa_annual_contrib_cap_krw: Dec = Decimal("20000000")
    pension_deduct_cap_savings_krw: Dec = Decimal("6000000")
    pension_deduct_cap_total_krw: Dec = Decimal("9000000")
    pension_contrib_cap_total_krw: Dec = Decimal("18000000")
    harvest_cost_gate_factor: Dec = Decimal("0.5")
    harvest_annual_nav_cap: Dec = Decimal("0.20")
    crypto_tax_enabled: bool = False


class TaxVersion(BaseModel):
    """One dated tax-law version and its human review note."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_from: date
    note: str = ""
    params: TaxParams

    @field_validator("params", mode="before")
    @classmethod
    def _inherit_effective_from(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, Mapping):
            return value
        if "effective_from" in value:
            raise ValueError("params.effective_from is derived from the version row")
        effective_from = info.data.get("effective_from")
        if effective_from is None:
            return value
        return {**value, "effective_from": effective_from}


class TaxLawFile(BaseModel):
    """The single-file effective-date history stored in ``config/tax.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    versions: tuple[TaxVersion, ...] = Field(min_length=1)

    @field_validator("versions")
    @classmethod
    def _normalize_versions(cls, value: tuple[TaxVersion, ...]) -> tuple[TaxVersion, ...]:
        counts = Counter(version.effective_from for version in value)
        duplicates = sorted(day for day, count in counts.items() if count > 1)
        if duplicates:
            rendered = ", ".join(day.isoformat() for day in duplicates)
            raise ValueError(f"effective_from dates must be unique (duplicates={rendered})")
        return tuple(sorted(value, key=lambda version: version.effective_from, reverse=True))

    def to_versioned(self) -> VersionedFile[TaxParams]:
        """Expose the validated history through the generic date-selection boundary."""
        return VersionedFile(
            tuple((version.effective_from, version.params) for version in self.versions)
        )


__all__ = ["TaxLawFile", "TaxParams", "TaxVersion"]
