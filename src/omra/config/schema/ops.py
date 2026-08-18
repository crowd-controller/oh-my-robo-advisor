"""Runtime, scheduler, monitoring, and data configuration models."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omra.core import Dec


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuntimeCfg(_FrozenModel):
    role: Literal["app", "tools"] = "app"
    fill_queue_warn: int = 1_000


class ToolsCfg(_FrozenModel):
    snapshot_max_age_h: int = 168


class WatchdogCfg(_FrozenModel):
    interval_sec: int = 10
    heartbeat_max_age_sec: int = 180
    loop_lag_exit_ms: int = 5_000
    consecutive: int = 3
    crashloop_window_min: int = 10
    crashloop_max: int = 3


class WebCfg(_FrozenModel):
    bind_host: str = "0.0.0.0"  # noqa: S104 - canonical host binding; C-37 guards live
    bind_port: int = 8_080
    public_exposed: bool = False
    https: bool = False
    session_idle_hours: int = 12
    session_max_days: int = 30
    request_budget_ms: int = 2_000
    shutdown_grace_sec: int = 5


class JobOverrideCfg(_FrozenModel):
    budget_sec: int | None = None
    enabled: bool = True


class PlannerStepValuesCfg(_FrozenModel):
    token_refresh_sec: int = 30
    approval_key_sec: int = 60
    calendar_crosscheck_sec: int = 30
    fx_snapshot_sec: int = 30
    inflow_waterfall_sec: int = 45
    secret_expiry_sec: int = 5
    presence_ladder_sec: int = 5
    health_snapshot_sec: int = 10
    register_dynamic_sec: int = 5
    labs_canary_eval_sec: int = 5
    surveillance_sec: int = 300


class PlannerStepsCfg(_FrozenModel):
    steps: PlannerStepValuesCfg = Field(default_factory=PlannerStepValuesCfg)


class CatchupCfg(_FrozenModel):
    serial: bool = True


class DepWaitCfg(_FrozenModel):
    universe_reeval_min: int = 30
    master_diff_min: int = 30


class JobsCfg(_FrozenModel):
    overrides: Mapping[str, JobOverrideCfg] = Field(default_factory=dict)
    planner: PlannerStepsCfg = Field(default_factory=PlannerStepsCfg)
    us_submit_lead: int = 10
    catchup: CatchupCfg = Field(default_factory=CatchupCfg)
    dep_wait: DepWaitCfg = Field(default_factory=DepWaitCfg)


class DiskCfg(_FrozenModel):
    warn_pct: int = 80
    block_pct: int = 90
    release_pct: int = 85


class LogsCfg(_FrozenModel):
    retention_days: int = 14
    retention_days_pressure: int = 7
    research_inbox_retention_months: int = 13


class DmsCfg(_FrozenModel):
    ping_url: str | None = None
    ping_interval_min: int = 15


class HealthCfg(_FrozenModel):
    thresholds: Mapping[str, int | str | None] = Field(default_factory=dict)


class MonitoringCfg(_FrozenModel):
    heartbeat_interval_sec: int = 30
    disk: DiskCfg = Field(default_factory=DiskCfg)
    logs: LogsCfg = Field(default_factory=LogsCfg)
    dms: DmsCfg = Field(default_factory=DmsCfg)
    health: HealthCfg = Field(default_factory=HealthCfg)


class DataQualityCfg(_FrozenModel):
    max_abs_daily_return: Dec = Decimal("0.3")
    max_abs_daily_return_crypto: Dec = Decimal("0.5")


class DataMasterCfg(_FrozenModel):
    files: tuple[str, ...] = ("kospi_code.mst.zip", "kosdaq_code.mst.zip")


class ProviderCfg(_FrozenModel):
    enabled: bool = True


class DataCfg(_FrozenModel):
    quality: DataQualityCfg = Field(default_factory=DataQualityCfg)
    master: DataMasterCfg = Field(default_factory=DataMasterCfg)
    providers: Mapping[str, ProviderCfg] = Field(default_factory=dict)


class SecretsPolicyCfg(_FrozenModel):
    ladder_days: tuple[int, ...] = (45, 30, 14, 7, 3, 1)
    issue_spacing_days: int = 180
