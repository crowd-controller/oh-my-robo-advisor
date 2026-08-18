"""Research and challenger-lab configuration models."""

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omra.config.schema.policy import CanaryStepCfg
from omra.core import Dec


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResearchSourceCfg(_FrozenModel):
    enabled: bool
    priority: Literal["P0", "P1", "P2"]


def _default_research_sources() -> dict[str, ResearchSourceCfg]:
    return {
        "github_releases": ResearchSourceCfg(enabled=True, priority="P0"),
        "pypi_json": ResearchSourceCfg(enabled=True, priority="P0"),
        "kis_repo": ResearchSourceCfg(enabled=True, priority="P0"),
        "kr_tax_notice": ResearchSourceCfg(enabled=True, priority="P0"),
        "upbit_docs": ResearchSourceCfg(enabled=True, priority="P1"),
        "arxiv_qfin": ResearchSourceCfg(enabled=True, priority="P1"),
        "practitioner_rss": ResearchSourceCfg(enabled=True, priority="P1"),
        "skfolio_docs": ResearchSourceCfg(enabled=False, priority="P2"),
    }


def _default_llm_budget() -> dict[Literal["research_extract"], Decimal]:
    return {"research_extract": Decimal(0)}


class ResearchLlmCfg(_FrozenModel):
    model: str = "claude-opus-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    max_output_tokens: int = 4_096
    use_batch: bool = True
    monthly_budget_usd: Mapping[Literal["research_extract"], Dec] = Field(
        default_factory=_default_llm_budget
    )


class ResearchCfg(_FrozenModel):
    enabled: bool = False
    collect_cron: str = "0 4 * * 0"
    digest_cron: str = "0 5 1 * *"
    max_items_per_digest: int = 40
    max_chars_per_item: int = 8_000
    source_fail_streak_warn: int = 3
    citation_fail_rate_alert: Dec = Decimal("0.10")
    sources: Mapping[str, ResearchSourceCfg] = Field(default_factory=_default_research_sources)
    llm: ResearchLlmCfg = Field(default_factory=ResearchLlmCfg)
    user_agent: str = "omra-research/1.0 (+self-hosted; contact via operator)"
    inbox_root: Path = Path("/app/var/data/research/inbox")
    report_root: Path = Path("/app/var/reports/research")


class LabsG2Cfg(_FrozenModel):
    mode: Literal["full", "short", "disabled"] = "full"


def _labs_targets() -> CanaryStepCfg:
    return CanaryStepCfg(
        alphas=(Decimal("0.333"), Decimal("0.667"), Decimal("1.0")),
        days_per_step=5,
    )


def _labs_methods() -> CanaryStepCfg:
    return CanaryStepCfg(
        alphas=(Decimal("0.25"), Decimal("0.50"), Decimal("1.0")),
        days_per_step=20,
    )


def _labs_universe() -> CanaryStepCfg:
    return CanaryStepCfg(
        alphas=(Decimal("0.5"), Decimal("1.0")),
        days_per_step=10,
    )


class LabsCanaryCfg(_FrozenModel):
    targets_recalc: CanaryStepCfg = Field(default_factory=_labs_targets)
    method_swap: CanaryStepCfg = Field(default_factory=_labs_methods)
    universe_swap: CanaryStepCfg = Field(default_factory=_labs_universe)
    veto_window_hours: int = 72


class RollbackCfg(_FrozenModel):
    r1_te_residual_pp: Dec = Decimal("0.3")
    r1_breach_count: int = 2
    r2_guard_multiple: Dec = Decimal("2.0")
    r3_turnover_multiple: Dec = Decimal("1.3")
    r3_budget_consumption: Dec = Decimal("0.8")
    r4_exec_failure_multiple: Dec = Decimal("2.0")
    freeze_days_after_2_rollbacks: int = 90
    annual_rollback_alarm: int = 3


class LabsCfg(_FrozenModel):
    enabled: bool = False
    challenger_enabled: bool = False
    tuning_space: tuple[str, ...] = ()
    shadow_min_days: int = 126
    g2: LabsG2Cfg = Field(default_factory=LabsG2Cfg)
    canary: LabsCanaryCfg = Field(default_factory=LabsCanaryCfg)
    rollback: RollbackCfg = Field(default_factory=RollbackCfg)
