"""Change-budget and canary configuration models."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from omra.core import Dec


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChangeBudgetCfg(_FrozenModel):
    total_per_year: int = 6
    targets_per_year: int = 4
    params_per_year: int = 4
    logic_per_year: int = 2


class PolicyCfg(_FrozenModel):
    change_budget: ChangeBudgetCfg = Field(default_factory=ChangeBudgetCfg)
    auto_threshold_pp: Dec = Decimal(8)
    reject_threshold_pp: Dec = Decimal(20)
    auto_nocanary_threshold_pp: Dec = Decimal(3)


class CanaryStepCfg(_FrozenModel):
    alphas: tuple[Dec, ...]
    days_per_step: int


def _target_steps() -> CanaryStepCfg:
    return CanaryStepCfg(
        alphas=(Decimal("0.333"), Decimal("0.667"), Decimal("1.0")),
        days_per_step=5,
    )


def _methodology_steps() -> CanaryStepCfg:
    return CanaryStepCfg(
        alphas=(Decimal("0.25"), Decimal("0.50"), Decimal("1.0")),
        days_per_step=20,
    )


class CanaryCfg(_FrozenModel):
    targets: CanaryStepCfg = Field(default_factory=_target_steps)
    methodology: CanaryStepCfg = Field(default_factory=_methodology_steps)
