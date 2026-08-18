"""Portfolio engine and backtest configuration models."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omra.core import Dec


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RiskCfg(_FrozenModel):
    level: int = Field(default=6, ge=1, le=10)


class CoreCfg(_FrozenModel):
    min_weight: Dec = Decimal("0.80")


class MomentumSleeveCfg(_FrozenModel):
    enabled: bool = False
    cap: Dec = Decimal("0.10")
    pair: tuple[str, str] = ("VOO", "VXUS")
    return_basis: Literal["usd_total_return"] = "usd_total_return"
    dd_basis: Literal["sleeve_krw_peak_to_trough"] = "sleeve_krw_peak_to_trough"
    turnover_cap_annual: Dec = Decimal("2.00")


class SatelliteCfg(_FrozenModel):
    total_cap: Dec = Decimal("0.20")
    momentum: MomentumSleeveCfg = Field(default_factory=MomentumSleeveCfg)


class CashCfg(_FrozenModel):
    buffer: Dec = Decimal("0.01")
    frozen_reserve_alert_pct: Dec = Decimal("0.05")


class BlCfg(_FrozenModel):
    tau: Dec = Field(default=Decimal("0.025"), ge=Decimal("0.02"), le=Decimal("0.05"))
    delta_mkt: Dec = Field(default=Decimal("3.0"), ge=Decimal(2), le=Decimal(4))
    max_views: int = 3
    view_shift_cap: Dec = Decimal("0.015")


def _default_asset_cap_overrides() -> dict[str, Decimal]:
    return {"nasdaq": Decimal("0.10"), "reits": Decimal("0.05")}


class MvoCfg(_FrozenModel):
    lambda_risk_bounds: tuple[Dec, Dec] = (Decimal("0.5"), Decimal(30))
    turnover_gamma: Dec = Decimal("0.01")
    asset_cap: Dec = Decimal("0.40")
    asset_cap_overrides: Mapping[str, Dec] = Field(default_factory=_default_asset_cap_overrides)


class EwmaCfg(_FrozenModel):
    lam: Dec = Decimal("0.94")
    days: int = 60


class CovCfg(_FrozenModel):
    strategic: Literal["lw_constant_correlation"] = "lw_constant_correlation"
    lookback_days: int = 756
    monitor: EwmaCfg = Field(default_factory=EwmaCfg)
    condition_number_max: int = 1_000


class SanityCfg(_FrozenModel):
    hrp_divergence: Dec = Decimal("0.20")


class BandCfg(_FrozenModel):
    abs: Dec = Decimal("0.05")
    rel: Dec = Decimal("0.25")
    pension_scheduled_abs: Dec = Decimal("0.07")
    pension_scheduled_rel: Dec = Decimal("0.35")
    isa_abs: Dec = Decimal("0.07")
    isa_rel: Dec = Decimal("0.35")
    crypto_abs: Dec = Decimal("0.01")
    crypto_rel: Dec = Decimal("0.30")
    class_abs: Dec = Decimal("0.05")
    restore_fraction: Dec = Decimal("0.5")
    restore_mode: Literal["fraction", "destination"] = "fraction"
    restore_rho: Dec | None = None


class RebalanceCfg(_FrozenModel):
    cooldown_days: int = 5


class UniverseCfg(_FrozenModel):
    shrink_below_krw: int = 30_000_000
    restore_above_krw: int = 40_000_000


def _default_min_amount() -> dict[Literal["kr", "us", "upbit"], Decimal]:
    return {
        "kr": Decimal(50_000),
        "us": Decimal(100),
        "upbit": Decimal(10_000),
    }


class TradeCfg(_FrozenModel):
    min_amount: Mapping[Literal["kr", "us", "upbit"], Dec] = Field(
        default_factory=_default_min_amount
    )


class MomentumCfg(_FrozenModel):
    lookbacks: tuple[int, ...] = (3, 6, 9, 12)


def _default_crypto_mix() -> dict[str, Decimal]:
    return {"KRW-BTC": Decimal("0.70"), "KRW-ETH": Decimal("0.30")}


class CryptoCfg(_FrozenModel):
    enabled: bool = False
    target: Dec = Field(default=Decimal("0.03"), ge=Decimal("0.01"), le=Decimal("0.10"))
    cap: Dec = Decimal("0.10")
    mix: Mapping[str, Dec] = Field(default_factory=_default_crypto_mix)
    vol_target: Dec = Decimal("0.40")
    vol_scale_floor: Dec = Decimal("0.33")
    kimchi_halt: Dec = Decimal("0.08")
    kimchi_alert: Dec = Decimal("0.05")
    drop_guard_24h_pct: Dec = Decimal("-0.15")
    vol_scale_max_age_days: int = 10


class SuccessBands(_FrozenModel):
    green: Dec = Decimal("0.75")
    amber: Dec = Decimal("0.60")


class McCfg(_FrozenModel):
    paths: int = 5_000
    block: int = 6
    success_bands: SuccessBands = Field(default_factory=SuccessBands)
    cost_annual: Dec = Decimal("0.0035")
    inflation_annual: Dec = Decimal("0.02")


class GkCfg(_FrozenModel):
    guardrail: Dec = Decimal("0.20")
    adjust: Dec = Decimal("0.10")


class BacktestGatesCfg(_FrozenModel):
    core: str = "WF(5+1y) + lookahead 0건 + 스냅샷 회귀(config 포함)"
    satellite: str = "CPCV(21/5) + 이웃 ±25% + DSR>0.95 + 부트스트랩"
    challenger_years: int = 10


class BacktestCostsCfg(_FrozenModel):
    fee_kr: Dec = Decimal("0.00015")
    fee_us: Dec = Decimal("0.0009")
    fee_crypto: Dec = Decimal("0.0005")
    tax_sell_kr_stock: Dec = Decimal("0.0015")
    slip_kr_etf_bp: Dec = Decimal(5)
    slip_us_bp: Dec = Decimal(3)
    slip_crypto_bp: Dec = Decimal(10)
    fx_spread_roundtrip: Dec = Decimal("0.002")


class BacktestDataCfg(_FrozenModel):
    max_gap_pct: Dec = Decimal("0.5")


class LookaheadCfg(_FrozenModel):
    samples: int = 10
    weight_tolerance: Dec = Decimal("1e-9")


class AbsoluteFloorCfg(_FrozenModel):
    sharpe: Dec | None = None
    max_mdd: Dec | None = None


class SnapshotCfg(_FrozenModel):
    tolerance_pct: Dec | None = None
    absolute_floor: AbsoluteFloorCfg | None = None


def _default_benchmark_composition() -> dict[Literal["equity", "bond"], Decimal]:
    return {"equity": Decimal("0.60"), "bond": Decimal("0.40")}


class BenchmarkCfg(_FrozenModel):
    composition: Mapping[Literal["equity", "bond"], Dec] = Field(
        default_factory=_default_benchmark_composition
    )
    rebalance: Literal["annual"] = "annual"
    apply_costs: bool = True
    track: Literal["pretax"] = "pretax"


class BacktestTaxCfg(_FrozenModel):
    harvest_enabled: bool = True


class BacktestCfg(_FrozenModel):
    account_model: Literal["single", "multi"] = "single"
    gates: BacktestGatesCfg = Field(default_factory=BacktestGatesCfg)
    sim_mode: Literal["clean", "with_guards"] = "clean"
    costs: BacktestCostsCfg = Field(default_factory=BacktestCostsCfg)
    data: BacktestDataCfg = Field(default_factory=BacktestDataCfg)
    lookahead: LookaheadCfg = Field(default_factory=LookaheadCfg)
    snapshot: SnapshotCfg
    benchmark: BenchmarkCfg = Field(default_factory=BenchmarkCfg)
    tax: BacktestTaxCfg = Field(default_factory=BacktestTaxCfg)
    seed: int = 20_260_101
    us_fill_basis: Literal["close", "intraday_limit"] = "close"
