"""The single root model for scalar application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from omra.config.schema.accounts import AccountCfg
from omra.config.schema.engine import (
    BacktestCfg,
    BandCfg,
    BlCfg,
    CashCfg,
    CoreCfg,
    CovCfg,
    CryptoCfg,
    GkCfg,
    McCfg,
    MomentumCfg,
    MvoCfg,
    RebalanceCfg,
    RiskCfg,
    SanityCfg,
    SatelliteCfg,
    TradeCfg,
    UniverseCfg,
)
from omra.config.schema.execution import EtfCfg, ExecutionCfg, OrderCfg
from omra.config.schema.improve import LabsCfg, ResearchCfg
from omra.config.schema.observe import (
    FxCfg,
    GuardCfg,
    QuoteCfg,
    RealtimeCfg,
    SurveillanceCfg,
    WsCfg,
)
from omra.config.schema.ops import (
    DataCfg,
    JobsCfg,
    MonitoringCfg,
    RuntimeCfg,
    SecretsPolicyCfg,
    ToolsCfg,
    WatchdogCfg,
    WebCfg,
)
from omra.config.schema.policy import CanaryCfg, PolicyCfg
from omra.config.schema.protections import (
    AlertsCfg,
    PresenceCfg,
    ProtectionsCfg,
    SafeModeCfg,
    TrackingErrorCfg,
)
from omra.config.schema.run import RunCfg
from omra.config.schema.taxcfg import TaxCfg, WaterfallCfg


class AppConfig(BaseSettings):
    """Immutable strict union of every scalar configuration block."""

    model_config = SettingsConfigDict(
        extra="forbid",
        env_prefix="OMRA__",
        env_nested_delimiter="__",
        frozen=True,
    )

    run: RunCfg
    accounts: tuple[AccountCfg, ...]

    risk: RiskCfg
    core: CoreCfg
    satellite: SatelliteCfg
    cash: CashCfg
    bl: BlCfg
    mvo: MvoCfg
    cov: CovCfg
    sanity: SanityCfg
    band: BandCfg
    rebalance: RebalanceCfg
    universe: UniverseCfg
    trade: TradeCfg
    momentum: MomentumCfg
    crypto: CryptoCfg
    mc: McCfg
    gk: GkCfg
    backtest: BacktestCfg

    order: OrderCfg
    execution: ExecutionCfg
    etf: EtfCfg

    tax: TaxCfg
    waterfall: WaterfallCfg

    protections: ProtectionsCfg
    safe_mode: SafeModeCfg
    presence: PresenceCfg
    tracking_error: TrackingErrorCfg
    alerts: AlertsCfg

    ws: WsCfg
    quote: QuoteCfg
    fx: FxCfg
    guard: GuardCfg
    realtime: RealtimeCfg
    surveillance: SurveillanceCfg

    research: ResearchCfg
    labs: LabsCfg

    policy: PolicyCfg
    canary: CanaryCfg

    data: DataCfg
    watchdog: WatchdogCfg
    runtime: RuntimeCfg
    tools: ToolsCfg
    web: WebCfg
    secrets: SecretsPolicyCfg
    jobs: JobsCfg
    monitoring: MonitoringCfg
