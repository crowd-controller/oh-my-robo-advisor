"""Safety, presence, and alert configuration models."""

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omra.core import Dec

_KST_TIME = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
_NEGATIVE_ISO_MINUTES = re.compile(r"^-PT[1-9][0-9]*M$")


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProtectionsCfg(_FrozenModel):
    mdd_safe_mode_pct: Dec = Decimal(-15)
    mdd_halt_pct: Dec = Decimal(-25)
    mdd_recover_pct: Dec = Decimal(-10)
    mdd_recover_days: int = 5
    daily_order_count: int = 30
    daily_order_amount_pct: Dec = Decimal(30)
    daily_order_amount_abs_krw: int | None = None
    symbol_cooldown_hits: int = 3
    symbol_cooldown_hours: int = 24
    symbol_cooldown_window_min: int = 60
    price_outlier_pct: Dec = Decimal(15)
    price_outlier_pct_crypto: Dec = Decimal(30)
    quote_stale_min: int = 5
    spread_max_pct: Dec = Decimal("1.0")
    reconcile_tolerance_shares: int = 0
    reconcile_tolerance_cash_krw: int | None = None
    error_streak_order: int = 5
    error_streak_quote: int = 5
    turnover_monthly_mult_warn: Dec = Decimal(2)
    turnover_monthly_mult_halt: Dec = Decimal(3)
    turnover_annual_assumption: Dec = Decimal("0.30")
    turnover_carryover_cap_days: int = 60
    turnover_streak_safe_mode: int = 3
    surveillance_stale_hours: int = 24
    frozen_nav_safe_mode_pct: Dec = Decimal(20)
    frozen_nav_halt_pct: Dec = Decimal(40)
    deadline_pause_days: int = 3
    event_burst_abs: int = 4
    event_burst_ratio: Dec = Decimal("0.30")


class SafeModeCfg(_FrozenModel):
    net_buy_daily_cap_pct: Dec = Decimal(3)
    net_buy_monthly_cap_pct: Dec = Decimal(10)
    net_buy_monthly_window_days: int = 30
    order_size_divisor: int = 3
    band_multiplier: Dec = Decimal(2)


class GraceCapCfg(_FrozenModel):
    crypto: str = "08:55"
    krx: str = "09:45"
    us_loc: str = "-PT30M"

    @field_validator("crypto", "krx")
    @classmethod
    def _validate_kst_time(cls, value: str) -> str:
        if _KST_TIME.fullmatch(value) is None:
            msg = "grace cap must be an HH:MM KST time"
            raise ValueError(msg)
        return value

    @field_validator("us_loc")
    @classmethod
    def _validate_relative_offset(cls, value: str) -> str:
        if _NEGATIVE_ISO_MINUTES.fullmatch(value) is None:
            msg = "US LOC grace cap must be a negative ISO-8601 minute duration"
            raise ValueError(msg)
        return value


class PresenceCfg(_FrozenModel):
    away_soft_h: int = 24
    away_h: int = 72
    away_long_d: int = 7
    grace_normal_min: int = 30
    grace_away_soft_h: int = 4
    grace_away_h: int = 12
    halt_downgrade_no_response_h: int = 24
    grace_cap_kst: GraceCapCfg = Field(default_factory=GraceCapCfg)


class AlertsCfg(_FrozenModel):
    guard_verdict_default: Literal["silent", "info"] = "silent"
    surveillance_state_entry: Literal["info", "warning"] = "info"
    critical_channels: tuple[Literal["telegram", "smtp", "webhook"], ...] = (
        "telegram",
        "smtp",
    )
    both_channels_fail_safe_mode_days: int = 2
    info_immediate_max_per_day: int = 5


class TrackingErrorCfg(_FrozenModel):
    residual_monthly_threshold_pp: Dec = Decimal("0.3")
