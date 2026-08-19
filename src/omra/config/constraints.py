"""Deterministic cross-file configuration constraints."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from omra.config.errors import Violation
from omra.config.files import SecretTier
from omra.config.schema.run import ExecEnv
from omra.core import AccountType, Broker

if TYPE_CHECKING:
    from pathlib import Path

    from omra.config import ConfigBundle

_ONE: Final = Decimal(1)
_WEIGHT_EPSILON: Final = Decimal("1e-9")
_FINANCIAL_INCOME_LIMIT: Final = 20_000_000
_WS_SUBSCRIPTION_HARD_CAP: Final = 41
_BL_DELTA_MIN: Final = Decimal(2)
_BL_DELTA_MAX: Final = Decimal(4)
_PLANNER_HARD_BUDGET_SEC: Final = 600
_LIVE_BIND_HOST: Final = "0.0.0.0"  # noqa: S104 - canonical live binding contract
_LIVE_CONFIRMATION = re.compile(r"^[0-9]{4}-I-UNDERSTAND$")
_CRYPTO_SYMBOLS: Final = frozenset({"KRW-BTC", "KRW-ETH"})
_REQUIRED_RISK_TYPES: Final = frozenset(
    {"KR-01", "KR-02", "KR-03", "KR-04", "KR-12", "US-01", "US-02"}
)
_TUNING_SPACE_ALLOWED: Final = frozenset(
    {
        "rebalance.cooldown_days",
        "mvo.turnover_gamma",
        "cov.lookback_days",
        "bl.tau",
    }
)
_TUNING_SPACE_EXACT_EXCLUDES: Final = frozenset(
    {"execution.max_open_orders", "bl.delta_mkt", "mvo.lambda_risk_bounds"}
)
_TUNING_SPACE_PREFIX_EXCLUDES: Final = (
    "band.",
    "safe_mode.",
    "protections.",
    "crypto.",
    "satellite.",
)


class ConstraintSeverity(StrEnum):
    """Whether a constraint rejects startup or only requests operator attention."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    """One stable-ID cross-field violation returned by check_all."""

    code: str
    message: str
    path: str
    severity: ConstraintSeverity = ConstraintSeverity.ERROR
    source: Path | None = None

    def as_config_violation(self) -> Violation:
        """Project this result into the loader's shared diagnostic shape."""
        return Violation(
            code=self.code,
            message=self.message,
            path=self.path,
            source=self.source,
        )

    def render(self) -> str:
        """Render an operator-facing diagnostic with the shared location format."""
        return self.as_config_violation().render()


def _record_source(bundle: ConfigBundle, filename: str) -> Path | None:
    return next((source.path for source in bundle.sources if source.path.name == filename), None)


def _add(
    violations: list[ConstraintViolation],
    violated: bool,
    *,
    code: str,
    message: str,
    path: str,
    severity: ConstraintSeverity = ConstraintSeverity.ERROR,
    source: Path | None = None,
) -> None:
    if violated:
        violations.append(
            ConstraintViolation(
                code=code,
                message=message,
                path=path,
                severity=severity,
                source=source,
            )
        )


def _strictly_increasing(values: tuple[Decimal, ...]) -> bool:
    return all(left < right for left, right in pairwise(values))


def _path_exists(root: BaseModel, dotted_path: str) -> bool:
    value: object = root
    for part in dotted_path.split("."):
        if isinstance(value, BaseModel):
            if part not in type(value).model_fields:
                return False
            value = getattr(value, part)
        elif isinstance(value, Mapping):
            if part not in value:
                return False
            value = value[part]
        else:
            return False
    return not isinstance(value, (BaseModel, Mapping))


def _is_tuning_excluded(path: str) -> bool:
    return path in _TUNING_SPACE_EXACT_EXCLUDES or path.startswith(_TUNING_SPACE_PREFIX_EXCLUDES)


def _invalid_canary_ladders(bundle: ConfigBundle) -> tuple[str, ...]:
    app = bundle.app
    ladders = (
        ("canary.targets.alphas", app.canary.targets.alphas),
        ("canary.methodology.alphas", app.canary.methodology.alphas),
        ("labs.canary.targets_recalc.alphas", app.labs.canary.targets_recalc.alphas),
        ("labs.canary.method_swap.alphas", app.labs.canary.method_swap.alphas),
        ("labs.canary.universe_swap.alphas", app.labs.canary.universe_swap.alphas),
    )
    return tuple(
        path
        for path, values in ladders
        if not values or not _strictly_increasing(values) or values[-1] != _ONE
    )


def _invalid_income_ladders(bundle: ConfigBundle) -> tuple[str, ...]:
    alert_sets = bundle.app.tax.income_alerts
    invalid: list[str] = []
    for name, values in (("api", alert_sets.api), ("fallback", alert_sets.fallback)):
        ordered = values.health <= values.info <= values.warn <= values.soft_stop
        if not ordered or values.soft_stop >= _FINANCIAL_INCOME_LIMIT:
            invalid.append(name)
    return tuple(invalid)


def _account_problems(bundle: ConfigBundle) -> tuple[list[str], list[str], int]:
    accounts = bundle.app.accounts
    counts = Counter(account.id for account in accounts)
    duplicates = sorted(account_id for account_id, count in counts.items() if count > 1)
    mismatches = sorted(
        account.id
        for account in accounts
        if (account.broker is Broker.UPBIT) != (account.type is AccountType.UPBIT)
    )
    enabled_general = sum(
        account.enabled and account.type is AccountType.GENERAL for account in accounts
    )
    return duplicates, mismatches, enabled_general


def _invalid_substitutes(bundle: ConfigBundle) -> tuple[str, ...]:
    classes: dict[str, set[str]] = {}
    for instrument in bundle.universe.instruments:
        classes.setdefault(instrument.symbol, set()).add(instrument.asset_class)

    invalid: list[str] = []
    for left, right in bundle.universe.approved_substitutes:
        left_classes = classes.get(left)
        right_classes = classes.get(right)
        if (
            left_classes is None
            or right_classes is None
            or len(left_classes) != 1
            or left_classes != right_classes
        ):
            invalid.append(f"{left}/{right}")
    return tuple(invalid)


def _issue_spacing_problems(bundle: ConfigBundle) -> tuple[str, ...]:
    entries = sorted(
        (
            entry
            for entry in bundle.registry.entries
            if entry.tier is SecretTier.TIER1 and entry.expires_at is not None
        ),
        key=lambda entry: (entry.issued_at, entry.name),
    )
    minimum = bundle.app.secrets.issue_spacing_days
    return tuple(
        f"{left.name}/{right.name}={(right.issued_at - left.issued_at).days}d"
        for left, right in pairwise(entries)
        if (right.issued_at - left.issued_at).days < minimum
    )


def _planner_total(bundle: ConfigBundle) -> int:
    steps = bundle.app.jobs.planner.steps
    return sum(
        (
            steps.token_refresh_sec,
            steps.approval_key_sec,
            steps.calendar_crosscheck_sec,
            steps.fx_snapshot_sec,
            steps.inflow_waterfall_sec,
            steps.secret_expiry_sec,
            steps.presence_ladder_sec,
            steps.health_snapshot_sec,
            steps.register_dynamic_sec,
            steps.labs_canary_eval_sec,
            steps.surveillance_sec,
        )
    )


def check_all(bundle: ConfigBundle) -> list[ConstraintViolation]:  # noqa: PLR0915
    """Return every bundle-resident constraint violation in canonical ID order.

    C-3 requires persisted budget counters, C-29 requires a Clock-selected tax
    version, and C-21's account-number equality requires Secrets. Those contextual
    checks remain outside this bundle-only boundary.
    """
    app = bundle.app
    violations: list[ConstraintViolation] = []

    _add(
        violations,
        app.band.abs > app.band.class_abs,
        code="C-1",
        message="band.abs must not exceed band.class_abs",
        path="band.abs",
    )
    budget = app.policy.change_budget
    child_budget = budget.targets_per_year + budget.params_per_year + budget.logic_per_year
    _add(
        violations,
        budget.total_per_year >= child_budget,
        code="C-2",
        message="total_per_year must be lower than the sum of child change budgets",
        path="policy.change_budget.total_per_year",
    )
    _add(
        violations,
        not (
            app.policy.auto_nocanary_threshold_pp
            < app.policy.auto_threshold_pp
            < app.policy.reject_threshold_pp
        ),
        code="C-4",
        message="policy thresholds must increase from no-canary through auto to reject",
        path="policy.auto_nocanary_threshold_pp",
    )
    _add(
        violations,
        app.core.min_weight < _ONE - app.satellite.total_cap,
        code="C-5",
        message="core.min_weight must cover the portfolio outside the satellite cap",
        path="core.min_weight",
    )
    _add(
        violations,
        app.satellite.momentum.cap + app.crypto.cap > app.satellite.total_cap,
        code="C-6",
        message="momentum and crypto caps must fit inside satellite.total_cap",
        path="satellite.total_cap",
    )
    _add(
        violations,
        app.crypto.target > app.crypto.cap,
        code="C-7",
        message="crypto.target must not exceed crypto.cap",
        path="crypto.target",
    )
    crypto_mix_invalid = (
        frozenset(app.crypto.mix) != _CRYPTO_SYMBOLS
        or sum(app.crypto.mix.values(), Decimal(0)) != _ONE
    )
    _add(
        violations,
        crypto_mix_invalid,
        code="C-8",
        message="crypto.mix must contain exactly KRW-BTC and KRW-ETH and sum to one",
        path="crypto.mix",
    )
    mdd_invalid = not (
        app.protections.mdd_halt_pct
        < app.protections.mdd_safe_mode_pct
        < app.protections.mdd_recover_pct
        < 0
    )
    _add(
        violations,
        mdd_invalid,
        code="C-9",
        message="MDD thresholds must increase from halt through safe-mode to recovery below zero",
        path="protections.mdd_halt_pct",
    )
    protections = app.protections
    c10_invalid = (
        protections.frozen_nav_safe_mode_pct >= protections.frozen_nav_halt_pct
        or protections.turnover_monthly_mult_warn >= protections.turnover_monthly_mult_halt
    )
    _add(
        violations,
        c10_invalid,
        code="C-10",
        message="safe-mode/warning thresholds must be lower than their halt thresholds",
        path="protections",
    )
    _add(
        violations,
        app.safe_mode.net_buy_daily_cap_pct > app.safe_mode.net_buy_monthly_cap_pct,
        code="C-11",
        message="daily net-buy cap must not exceed the monthly cap",
        path="safe_mode.net_buy_daily_cap_pct",
    )
    presence = app.presence
    c12_invalid = not (
        presence.away_soft_h < presence.away_h < presence.away_long_d * 24
        and presence.grace_normal_min
        <= presence.grace_away_soft_h * 60
        <= presence.grace_away_h * 60
    )
    _add(
        violations,
        c12_invalid,
        code="C-12",
        message="away and grace thresholds must be monotonically ordered",
        path="presence",
    )
    _add(
        violations,
        app.ws.subscription_cap + app.ws.reserve > _WS_SUBSCRIPTION_HARD_CAP,
        code="C-13",
        message="WebSocket subscription cap plus reserve must not exceed 41",
        path="ws.subscription_cap",
    )
    c14_invalid = (
        app.canary.targets != app.labs.canary.targets_recalc
        or app.canary.methodology != app.labs.canary.method_swap
    )
    _add(
        violations,
        c14_invalid,
        code="C-14",
        message="policy and labs canary ladders for the same change must match",
        path="canary",
    )
    invalid_ladders = _invalid_canary_ladders(bundle)
    _add(
        violations,
        bool(invalid_ladders),
        code="C-15",
        message="canary alphas must strictly increase and end at 1.0: "
        + ", ".join(invalid_ladders),
        path=invalid_ladders[0] if invalid_ladders else "canary",
    )
    invalid_income = _invalid_income_ladders(bundle)
    _add(
        violations,
        bool(invalid_income),
        code="C-16",
        message="income alert ladders must be ordered below 20,000,000: "
        + ", ".join(invalid_income),
        path=f"tax.income_alerts.{invalid_income[0]}" if invalid_income else "tax.income_alerts",
    )
    _add(
        violations,
        app.universe.shrink_below_krw >= app.universe.restore_above_krw,
        code="C-17",
        message="universe shrink threshold must be lower than its restore threshold",
        path="universe.shrink_below_krw",
    )
    lower, upper = app.mvo.lambda_risk_bounds
    c18_invalid = not (
        lower < upper
        and Decimal("0.02") <= app.bl.tau <= Decimal("0.05")
        and _BL_DELTA_MIN <= app.bl.delta_mkt <= _BL_DELTA_MAX
    )
    _add(
        violations,
        c18_invalid,
        code="C-18",
        message="MVO lambda bounds and BL tau/delta ranges must be ordered and in range",
        path="mvo.lambda_risk_bounds",
    )
    premium = app.etf.premium_gate
    _add(
        violations,
        premium.min_wait_sec > premium.max_total_defer_min * 60,
        code="C-19",
        message="premium-gate minimum wait must fit inside the maximum total defer window",
        path="etf.premium_gate.min_wait_sec",
    )
    invalid_tuning = tuple(
        path
        for path in app.labs.tuning_space
        if (
            not _path_exists(app, path)
            or path not in _TUNING_SPACE_ALLOWED
            or _is_tuning_excluded(path)
        )
    )
    _add(
        violations,
        bool(invalid_tuning),
        code="C-20",
        message="labs.tuning_space contains unknown or hard-excluded fields: "
        + ", ".join(invalid_tuning),
        path="labs.tuning_space",
    )
    live_confirmation_invalid = app.run.env is ExecEnv.LIVE and (
        app.run.live_confirmation is None
        or _LIVE_CONFIRMATION.fullmatch(app.run.live_confirmation) is None
    )
    crypto_account_missing = app.crypto.enabled and not any(
        account.enabled and account.broker is Broker.UPBIT and account.type is AccountType.UPBIT
        for account in app.accounts
    )
    _add(
        violations,
        live_confirmation_invalid or crypto_account_missing,
        code="C-21",
        message="live confirmation format or enabled crypto account requirement is not satisfied",
        path="run.live_confirmation" if live_confirmation_invalid else "accounts",
    )
    duplicates, mismatches, enabled_general = _account_problems(bundle)
    c22_invalid = bool(duplicates or mismatches) or (
        app.run.env is not ExecEnv.DRY_RUN and enabled_general != 1
    )
    _add(
        violations,
        c22_invalid,
        code="C-22",
        message=(
            "account IDs, broker/type pairing, or enabled general-account cardinality is invalid"
        ),
        path="accounts",
    )
    invalid_substitutes = _invalid_substitutes(bundle)
    _add(
        violations,
        bool(invalid_substitutes),
        code="C-23",
        message="approved substitutes must exist in one asset class: "
        + ", ".join(invalid_substitutes),
        path="approved_substitutes",
        source=_record_source(bundle, "universe.yaml"),
    )
    targets_invalid = False
    if bundle.targets is not None:
        target_total = sum(bundle.targets.weights.values(), Decimal(0)) + bundle.targets.cash
        targets_invalid = (
            abs(target_total - _ONE) > _WEIGHT_EPSILON
            or abs(bundle.targets.cash - app.cash.buffer) > _WEIGHT_EPSILON
        )
    _add(
        violations,
        targets_invalid,
        code="C-24",
        message="target weights plus cash must sum to one and target cash must match cash.buffer",
        path="weights",
        source=_record_source(bundle, "targets.yaml"),
    )
    top_ok = abs(sum(bundle.weights.top_level.values(), Decimal(0)) - _ONE) <= _WEIGHT_EPSILON
    regions = tuple(bundle.weights.equity_regions.weights.values())
    regions_ok = (
        any(value is None for value in regions)
        or abs(sum((value for value in regions if value is not None), Decimal(0)) - _ONE)
        <= _WEIGHT_EPSILON
    )
    _add(
        violations,
        not top_ok or not regions_ok,
        code="C-25",
        message="market top-level and available equity-region weights must each sum to one",
        path="top_level" if not top_ok else "equity_regions.weights",
        source=_record_source(bundle, "market_weights.yaml"),
    )
    invalid_schedules = tuple(
        schedule.id for schedule in bundle.schedules.root if schedule.amount_tolerance_krw <= 0
    )
    _add(
        violations,
        bool(invalid_schedules),
        code="C-26",
        message="external schedule amount tolerances must be positive: "
        + ", ".join(invalid_schedules),
        path="amount_tolerance_krw",
        source=_record_source(bundle, "external_schedules.yaml"),
    )
    spacing_problems = _issue_spacing_problems(bundle)
    _add(
        violations,
        bool(spacing_problems),
        code="C-27",
        message=(
            f"tier-1 issue dates are closer than {app.secrets.issue_spacing_days} days: "
            + ", ".join(spacing_problems)
        ),
        path="entries",
        severity=ConstraintSeverity.WARNING,
        source=_record_source(bundle, "secrets_registry.yaml"),
    )
    actual_risk_types = frozenset(entry.risk_type for entry in bundle.surv_map.map)
    missing_risk_types = sorted(_REQUIRED_RISK_TYPES - actual_risk_types)
    _add(
        violations,
        bool(missing_risk_types),
        code="C-28",
        message=f"surveillance map is missing required risk types: {missing_risk_types}",
        path="map",
        source=_record_source(bundle, "surveillance.yaml"),
    )
    planner_total = _planner_total(bundle)
    _add(
        violations,
        planner_total > _PLANNER_HARD_BUDGET_SEC,
        code="C-30",
        message=f"planner step budgets total {planner_total}s, exceeding the 600s hard budget",
        path="jobs.planner.steps",
    )
    band = app.band
    restore_valid = (band.restore_mode == "fraction" and band.restore_rho is None) or (
        band.restore_mode == "destination"
        and band.restore_rho is not None
        and 0 < band.restore_rho <= _ONE
    )
    _add(
        violations,
        not restore_valid,
        code="C-31",
        message="restore_rho must be in (0, 1] only for destination restore mode",
        path="band.restore_rho",
    )
    costs = app.backtest.costs
    cost_values = (
        costs.fee_kr,
        costs.fee_us,
        costs.fee_crypto,
        costs.tax_sell_kr_stock,
        costs.slip_kr_etf_bp,
        costs.slip_us_bp,
        costs.slip_crypto_bp,
        costs.fx_spread_roundtrip,
    )
    _add(
        violations,
        all(value == 0 for value in cost_values),
        code="C-32",
        message="backtest costs must not all be zero",
        path="backtest.costs",
    )
    snapshot = app.backtest.snapshot
    floor = snapshot.absolute_floor
    snapshot_invalid = (
        snapshot.tolerance_pct is None
        or floor is None
        or floor.sharpe is None
        or floor.max_mdd is None
    )
    _add(
        violations,
        snapshot_invalid,
        code="C-33",
        message="snapshot tolerance and both absolute-floor values must be configured",
        path="backtest.snapshot",
    )
    success = app.mc.success_bands
    _add(
        violations,
        not (0 < success.amber < success.green < _ONE),
        code="C-34",
        message="Monte Carlo success bands must satisfy 0 < amber < green < 1",
        path="mc.success_bands",
    )
    disk = app.monitoring.disk
    _add(
        violations,
        not (disk.warn_pct < disk.release_pct < disk.block_pct),
        code="C-35",
        message="disk thresholds must increase from warning through release to block",
        path="monitoring.disk",
    )
    _add(
        violations,
        app.labs.rollback.r1_te_residual_pp != app.tracking_error.residual_monthly_threshold_pp,
        code="C-36",
        message="labs rollback R1 and tracking-error residual thresholds must match",
        path="labs.rollback.r1_te_residual_pp",
    )
    c37_invalid = app.run.env is ExecEnv.LIVE and (
        app.web.public_exposed or app.web.bind_host != _LIVE_BIND_HOST
    )
    _add(
        violations,
        c37_invalid,
        code="C-37",
        message="live mode requires a private web surface bound to 0.0.0.0",
        path="web",
    )
    return violations


__all__ = ["ConstraintSeverity", "ConstraintViolation", "check_all"]
