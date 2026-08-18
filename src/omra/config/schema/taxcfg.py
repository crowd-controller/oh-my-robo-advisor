"""Tax and contribution-waterfall configuration models."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omra.core import Dec


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IncomeThresholdsCfg(_FrozenModel):
    health: int
    info: int
    warn: int
    soft_stop: int


def _api_thresholds() -> IncomeThresholdsCfg:
    return IncomeThresholdsCfg(
        health=10_000_000,
        info=12_000_000,
        warn=16_000_000,
        soft_stop=18_000_000,
    )


def _fallback_thresholds() -> IncomeThresholdsCfg:
    return IncomeThresholdsCfg(
        health=10_000_000,
        info=14_000_000,
        warn=18_000_000,
        soft_stop=19_000_000,
    )


class IncomeAlertSets(_FrozenModel):
    api: IncomeThresholdsCfg = Field(default_factory=_api_thresholds)
    fallback: IncomeThresholdsCfg = Field(default_factory=_fallback_thresholds)


class TaxCfg(_FrozenModel):
    harvest_start: str = "11-25"
    deduction: int = 2_500_000
    income_alerts: IncomeAlertSets = Field(default_factory=IncomeAlertSets)
    basis_price_source: Literal["api", "fallback"] = "fallback"
    isa_free_limit: int = 2_000_000
    isa_usage_alert: Dec = Decimal("0.70")
    isa_contract_start_date: date | None = None
    isa_usage_opening_amount: int | None = None
    isa_usage_opening_as_of: date | None = None
    harvest_rebuy_buffer_pct: Dec = Decimal("0.005")
    health_insurance_status: Literal["employee", "regional", "dependent"] = "regional"
    user_marginal_credit_rate: Dec = Decimal("0.132")
    crypto_tax_enabled: bool = False
    harvest_auto_enabled: bool = False


class WaterfallCfg(_FrozenModel):
    fill_pension_to_limit: bool = False
    pension_deduct_cap_total: int = 9_000_000
    pension_deduct_cap_savings: int = 6_000_000
    gap_check_date: str = "11-01"
    reminders: tuple[str, ...] = ("12-08", "12-15", "12-19")
    transfer_reserve_expiry_days: int = 7
