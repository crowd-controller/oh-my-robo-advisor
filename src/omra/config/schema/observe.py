"""Quote, real-time guard, and surveillance configuration models."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omra.core import Dec


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class WsCfg(_FrozenModel):
    tier1_execution_window_only: bool = True
    tier1_enabled: bool = False
    subscription_cap: int = 38
    reserve: int = 3
    max_active_symbols: int = 9


def _default_quote_ages() -> dict[Literal["krx", "upbit", "us"], int | None]:
    return {"krx": 2_000, "upbit": 2_000, "us": None}


class QuoteCfg(_FrozenModel):
    max_age_ms: Mapping[Literal["krx", "upbit", "us"], int | None] = Field(
        default_factory=_default_quote_ages
    )


class FxCfg(_FrozenModel):
    max_age_hours: int = 72


class MoveGuardCfg(_FrozenModel):
    window_sec: int = 300
    nav_weighted_move_pct: Dec = Decimal("3.0")
    min_symbols: int = 2
    min_samples: int = 5


class GuardCfg(_FrozenModel):
    oneway: Literal[True] = True
    min_duration_sec: int = 30
    move_guard: MoveGuardCfg = Field(default_factory=MoveGuardCfg)


class RealtimeCfg(_FrozenModel):
    rest_fallback_poll_sec: int = 30
    upbit_maintenance_fail_streak: int = 3


class SurvSourceCfg(_FrozenModel):
    enabled: bool
    grade: Literal["official"] = "official"
    max_auto_level: Literal["SV0", "SV1", "SV2", "SV3"] = "SV3"
    max_age_trading_days: int | None = None
    max_age_hours: int | None = None


def _source(enabled: bool, *, max_age_hours: int | None = None) -> SurvSourceCfg:
    return SurvSourceCfg(enabled=enabled, max_age_hours=max_age_hours)


def _default_surveillance_sources() -> dict[str, SurvSourceCfg]:
    return {
        "kis_master": _source(True),
        "kis_stock_info": _source(True),
        "kis_ksdinfo": _source(True),
        "kis_overseas": _source(False),
        "upbit_market": _source(False, max_age_hours=12),
        "kis_ws_market": _source(False),
    }


class SurveillanceCfg(_FrozenModel):
    max_age_trading_days: int = 2
    unknown_default_level: Literal["SV0", "SV1", "SV2", "SV3"] = "SV2"
    override_max_days: int = 90
    override_clear_max_days: int = 30
    daily_poll_timeout_sec: int = 300
    sources: Mapping[str, SurvSourceCfg] = Field(default_factory=_default_surveillance_sources)
