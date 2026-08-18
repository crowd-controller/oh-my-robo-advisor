"""Order and execution configuration models."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omra.core import Dec, SleeveId


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RepriceCfg(_FrozenModel):
    interval_min: int = 5
    max_count: int = 3


class OrderCfg(_FrozenModel):
    max_amount_krw: int = 5_000_000
    reprice: RepriceCfg = Field(default_factory=RepriceCfg)
    us_strategy: Literal["loc", "intraday_limit"] = "loc"


def _default_open_orders() -> dict[SleeveId, int]:
    return {
        SleeveId.KIS_DOMESTIC: 6,
        SleeveId.KIS_OVERSEAS: 6,
        SleeveId.UPBIT: 4,
    }


class ExecutionCfg(_FrozenModel):
    max_open_orders: Mapping[SleeveId, int] = Field(default_factory=_default_open_orders)


class PremiumGateCfg(_FrozenModel):
    threshold_pct: Dec = Decimal("0.5")
    threshold_ticks: int = 3
    rest_defer_minutes: int = 30
    max_defer_count: int = 3
    min_wait_sec: int = 300
    max_total_defer_min: int = 90


class EtfCfg(_FrozenModel):
    premium_gate: PremiumGateCfg = Field(default_factory=PremiumGateCfg)
