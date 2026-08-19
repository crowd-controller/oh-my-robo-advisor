"""Table contracts for bundle-resident configuration constraints."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import BaseModel

from omra.config import (
    AppConfig,
    ConfigBundle,
    ConfigFingerprint,
    ConstraintSeverity,
    check_all,
)
from omra.config.files import (
    ExternalIncomeFile,
    ExternalSchedule,
    ExternalSchedulesFile,
    GoalsFile,
    MarketWeightsFile,
    OpenQuestionsFile,
    SecretRegistryEntry,
    SecretsRegistryFile,
    SurveillanceMapFile,
    TargetsFile,
    TaxParams,
    TrIdsRaw,
    UniverseFile,
    UniverseInstrument,
)
from omra.config.schema.accounts import AccountCfg
from omra.config.schema.run import ExecEnv
from omra.config.versioned import VersionedFile
from omra.core import Market, TickRuleId

if TYPE_CHECKING:
    from collections.abc import Mapping

_CODES = (
    "C-1",
    "C-2",
    *(f"C-{number}" for number in range(4, 29)),
    *(f"C-{number}" for number in range(30, 38)),
)
_EXPECTED_PATHS = {
    "C-1": "band.abs",
    "C-2": "policy.change_budget.total_per_year",
    "C-4": "policy.auto_nocanary_threshold_pp",
    "C-5": "core.min_weight",
    "C-6": "satellite.total_cap",
    "C-7": "crypto.target",
    "C-8": "crypto.mix",
    "C-9": "protections.mdd_halt_pct",
    "C-10": "protections",
    "C-11": "safe_mode.net_buy_daily_cap_pct",
    "C-12": "presence",
    "C-13": "ws.subscription_cap",
    "C-14": "canary",
    "C-15": "canary.targets.alphas",
    "C-16": "tax.income_alerts.api",
    "C-17": "universe.shrink_below_krw",
    "C-18": "mvo.lambda_risk_bounds",
    "C-19": "etf.premium_gate.min_wait_sec",
    "C-20": "labs.tuning_space",
    "C-21": "accounts",
    "C-22": "accounts",
    "C-23": "approved_substitutes",
    "C-24": "weights",
    "C-25": "top_level",
    "C-26": "amount_tolerance_krw",
    "C-27": "entries",
    "C-28": "map",
    "C-30": "jobs.planner.steps",
    "C-31": "band.restore_rho",
    "C-32": "backtest.costs",
    "C-33": "backtest.snapshot",
    "C-34": "mc.success_bands",
    "C-35": "monitoring.disk",
    "C-36": "labs.rollback.r1_te_residual_pp",
    "C-37": "web",
}


def _app() -> AppConfig:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["accounts"] = []
    values["backtest"] = {
        "snapshot": {
            "tolerance_pct": "0.05",
            "absolute_floor": {"sharpe": "0", "max_mdd": "-1"},
        }
    }
    return AppConfig.model_validate(values)


def _trids() -> TrIdsRaw:
    return TrIdsRaw.model_validate(
        {
            "rest": {
                "live_prefix": "T",
                "paper_prefix": "V",
                "base_url": {
                    "live": "https://live.example.test",
                    "paper": "https://paper.example.test",
                },
                "trs": [],
            },
            "ws": {
                "live": {
                    "url": "wss://live.example.test",
                    "port": 21000,
                    "tr": {
                        "exec_notice_domestic": "H0STCNI0",
                        "exec_notice_overseas": "H0GSCNI0",
                    },
                },
                "paper": {
                    "url": "wss://paper.example.test",
                    "port": 21001,
                    "tr": {
                        "exec_notice_domestic": "H0STCNI0",
                        "exec_notice_overseas": "H0GSCNI0",
                    },
                },
            },
        }
    )


def _surveillance() -> SurveillanceMapFile:
    return SurveillanceMapFile.model_validate(
        {
            "version": 1,
            "map": [
                {"risk_type": "KR-01", "level": "SV3"},
                {"risk_type": "KR-02", "level": "SV2"},
                {"risk_type": "KR-03", "level": "SV2"},
                {"risk_type": "KR-04", "level": "SV2"},
                {"risk_type": "KR-12", "level": "SV3"},
                {"risk_type": "US-01", "level": "SV3"},
                {"risk_type": "US-02", "level": "SV2"},
            ],
        }
    )


def _bundle() -> ConfigBundle:
    tax_day = date(2026, 1, 1)
    return ConfigBundle(
        app=_app(),
        universe=UniverseFile(
            version=1,
            approved_at=date(2026, 8, 1),
            instruments=(),
        ),
        targets=None,
        goals=GoalsFile.model_validate({"goals": [], "glide_path": {}}),
        weights=MarketWeightsFile.model_validate(
            {
                "version": 1,
                "as_of": "2026-08-01",
                "top_level": {"equity": "0.45", "bond": "0.45", "alternative": "0.10"},
                "equity_regions": {
                    "source": "msci_acwi_imi",
                    "weights": {"kr": "0.10", "us": "0.60", "dev_ex_us": "0.30"},
                },
            }
        ),
        schedules=ExternalSchedulesFile.model_validate([]),
        income=ExternalIncomeFile.model_validate([]),
        surv_map=_surveillance(),
        tax=VersionedFile(((tax_day, TaxParams(effective_from=tax_day)),)),
        registry=SecretsRegistryFile.model_validate([]),
        trids=_trids(),
        questions=OpenQuestionsFile(version=1, questions=()),
        sources=(),
        fingerprint=ConfigFingerprint(files={}, effective="sha256:test"),
    )


def _update_model(
    model: BaseModel,
    path: tuple[str, ...],
    updates: Mapping[str, object],
) -> BaseModel:
    if not path:
        return model.model_copy(update=dict(updates))
    child = getattr(model, path[0])
    assert isinstance(child, BaseModel)
    changed = _update_model(child, path[1:], updates)
    return model.model_copy(update={path[0]: changed})


def _app_update(
    bundle: ConfigBundle,
    path: tuple[str, ...],
    **updates: object,
) -> ConfigBundle:
    app = cast("AppConfig", _update_model(bundle.app, path, updates))
    return replace(bundle, app=app)


def _account(
    account_id: str = "general01",
    *,
    account_type: str = "general",
    broker: str = "KIS",
) -> AccountCfg:
    return AccountCfg.model_validate(
        {
            "id": account_id,
            "type": account_type,
            "broker": broker,
            "mode": "AUTO",
        }
    )


def _instrument(symbol: str, asset_class: str) -> UniverseInstrument:
    return UniverseInstrument.model_validate(
        {
            "symbol": symbol,
            "market": Market.KRX,
            "currency": "KRW",
            "asset_class": asset_class,
            "sleeve": "core",
            "tax_inefficiency_score": 4,
            "risk_asset": True,
            "lot_step": "1",
            "tick_rule": TickRuleId.KRX_ETF_5,
            "allowed_accounts": ["general"],
            "account_preference": {"general": 1},
        }
    )


def _violate(  # noqa: PLR0911, PLR0912, PLR0915
    code: str,
    bundle: ConfigBundle,
) -> ConfigBundle:
    app = bundle.app
    match code:
        case "C-1":
            return _app_update(bundle, ("band",), abs=Decimal("0.06"))
        case "C-2":
            budget = app.policy.change_budget.model_copy(update={"total_per_year": 10})
            return _app_update(bundle, ("policy",), change_budget=budget)
        case "C-4":
            return _app_update(
                bundle,
                ("policy",),
                auto_nocanary_threshold_pp=Decimal(9),
            )
        case "C-5":
            return _app_update(bundle, ("core",), min_weight=Decimal("0.79"))
        case "C-6":
            momentum = app.satellite.momentum.model_copy(update={"cap": Decimal("0.11")})
            return _app_update(bundle, ("satellite",), momentum=momentum)
        case "C-7":
            return _app_update(bundle, ("crypto",), target=Decimal("0.11"))
        case "C-8":
            return _app_update(
                bundle,
                ("crypto",),
                mix={"KRW-BTC": Decimal("0.60"), "KRW-ETH": Decimal("0.30")},
            )
        case "C-9":
            return _app_update(bundle, ("protections",), mdd_halt_pct=Decimal(-14))
        case "C-10":
            return _app_update(
                bundle,
                ("protections",),
                frozen_nav_safe_mode_pct=Decimal(40),
            )
        case "C-11":
            return _app_update(
                bundle,
                ("safe_mode",),
                net_buy_daily_cap_pct=Decimal(11),
            )
        case "C-12":
            return _app_update(bundle, ("presence",), away_soft_h=72)
        case "C-13":
            return _app_update(bundle, ("ws",), subscription_cap=39)
        case "C-14":
            canary_targets = app.canary.targets.model_copy(update={"days_per_step": 6})
            return _app_update(bundle, ("canary",), targets=canary_targets)
        case "C-15":
            alphas = (Decimal("0.5"), Decimal("0.4"), Decimal(1))
            targets = app.canary.targets.model_copy(update={"alphas": alphas})
            changed = _app_update(bundle, ("canary",), targets=targets)
            labs_targets = changed.app.labs.canary.targets_recalc.model_copy(
                update={"alphas": alphas}
            )
            return _app_update(
                changed,
                ("labs", "canary"),
                targets_recalc=labs_targets,
            )
        case "C-16":
            api = app.tax.income_alerts.api.model_copy(update={"info": 9_000_000})
            return _app_update(bundle, ("tax", "income_alerts"), api=api)
        case "C-17":
            return _app_update(bundle, ("universe",), shrink_below_krw=40_000_000)
        case "C-18":
            return _app_update(
                bundle,
                ("mvo",),
                lambda_risk_bounds=(Decimal(30), Decimal("0.5")),
            )
        case "C-19":
            return _app_update(bundle, ("etf", "premium_gate"), min_wait_sec=5_401)
        case "C-20":
            return _app_update(bundle, ("labs",), tuning_space=("band.abs",))
        case "C-21":
            return _app_update(bundle, ("crypto",), enabled=True)
        case "C-22":
            accounts = (_account("duplicate"), _account("duplicate"))
            return _app_update(bundle, (), accounts=accounts)
        case "C-23":
            universe = UniverseFile(
                version=1,
                approved_at=date(2026, 8, 1),
                instruments=(
                    _instrument("360750", "kr_etf_equity"),
                    _instrument("114800", "kr_etf_bond"),
                ),
                approved_substitutes=(("360750", "114800"),),
            )
            return replace(bundle, universe=universe)
        case "C-24":
            target_file = TargetsFile.model_validate(
                {
                    "version": 1,
                    "as_of": "2026-08-01",
                    "risk_level": 6,
                    "weights": {"KRX:360750": "0.40"},
                    "cash": "0.50",
                }
            )
            return replace(bundle, targets=target_file)
        case "C-25":
            weights = bundle.weights.model_copy(
                update={
                    "top_level": {
                        "equity": Decimal("0.40"),
                        "bond": Decimal("0.40"),
                        "alternative": Decimal("0.10"),
                    }
                }
            )
            return replace(bundle, weights=weights)
        case "C-26":
            schedule = ExternalSchedule.model_validate(
                {
                    "id": "monthly_cash",
                    "account_id": "general01",
                    "kind": "cash_in",
                    "day_of_month": 1,
                    "holiday_shift": "next_business_day",
                    "amount_krw": 100_000,
                    "amount_tolerance_krw": 1,
                    "start_date": "2026-01-01",
                }
            ).model_copy(update={"amount_tolerance_krw": 0})
            schedules = bundle.schedules.model_copy(update={"root": (schedule,)})
            return replace(bundle, schedules=schedules)
        case "C-27":
            first = SecretRegistryEntry.model_validate(
                {
                    "name": "KIS_APP_KEY",
                    "issued_at": "2026-01-01",
                    "expires_at": "2027-01-01",
                    "tier": 1,
                    "auto_action": "pause_all_d7_safe_mode_d3",
                }
            )
            second = SecretRegistryEntry.model_validate(
                {
                    "name": "UPBIT_ACCESS",
                    "issued_at": "2026-02-01",
                    "expires_at": "2027-02-01",
                    "tier": 1,
                    "auto_action": "pause_all_d7_safe_mode_d3",
                }
            )
            registry = SecretsRegistryFile.model_validate([first, second])
            return replace(bundle, registry=registry)
        case "C-28":
            surv_map = bundle.surv_map.model_copy(
                update={
                    "map": tuple(
                        entry for entry in bundle.surv_map.map if entry.risk_type != "US-02"
                    )
                }
            )
            return replace(bundle, surv_map=surv_map)
        case "C-30":
            return _app_update(
                bundle,
                ("jobs", "planner", "steps"),
                surveillance_sec=376,
            )
        case "C-31":
            return _app_update(
                bundle,
                ("band",),
                restore_mode="destination",
                restore_rho=None,
            )
        case "C-32":
            zero_costs = app.backtest.costs.model_copy(
                update={name: Decimal(0) for name in type(app.backtest.costs).model_fields}
            )
            return _app_update(bundle, ("backtest",), costs=zero_costs)
        case "C-33":
            snapshot = app.backtest.snapshot.model_copy(update={"tolerance_pct": None})
            return _app_update(bundle, ("backtest",), snapshot=snapshot)
        case "C-34":
            bands = app.mc.success_bands.model_copy(
                update={"green": Decimal("0.50"), "amber": Decimal("0.60")}
            )
            return _app_update(bundle, ("mc",), success_bands=bands)
        case "C-35":
            return _app_update(bundle, ("monitoring", "disk"), release_pct=95)
        case "C-36":
            return _app_update(
                bundle,
                ("labs", "rollback"),
                r1_te_residual_pp=Decimal("0.4"),
            )
        case "C-37":
            changed = _app_update(
                bundle,
                (),
                accounts=(_account(),),
            )
            changed = _app_update(
                changed,
                ("run",),
                env=ExecEnv.LIVE,
                live_confirmation="1234-I-UNDERSTAND",
            )
            return _app_update(changed, ("web",), public_exposed=True)
        case _:
            raise AssertionError(f"unknown constraint fixture: {code}")


def test_canonical_default_bundle_has_no_static_constraint_violation() -> None:
    assert check_all(_bundle()) == []


@pytest.mark.parametrize("code", _CODES)
def test_each_bundle_constraint_reports_exact_id(code: str) -> None:
    violations = check_all(_violate(code, _bundle()))

    assert [violation.code for violation in violations] == [code]
    assert violations[0].path == _EXPECTED_PATHS[code]
    expected = ConstraintSeverity.WARNING if code == "C-27" else ConstraintSeverity.ERROR
    assert violations[0].severity is expected


def test_multiple_violations_are_returned_in_canonical_numeric_order() -> None:
    bundle = _violate("C-1", _violate("C-37", _bundle()))

    assert [violation.code for violation in check_all(bundle)] == ["C-1", "C-37"]


def test_all_four_canonical_tuning_paths_are_accepted() -> None:
    bundle = _app_update(
        _bundle(),
        ("labs",),
        tuning_space=(
            "rebalance.cooldown_days",
            "mvo.turnover_gamma",
            "cov.lookback_days",
            "bl.tau",
        ),
    )

    assert check_all(bundle) == []


def test_live_confirmation_requires_the_static_four_digit_acknowledgement_shape() -> None:
    bundle = _app_update(_bundle(), (), accounts=(_account(),))
    bundle = _app_update(
        bundle,
        ("run",),
        env=ExecEnv.LIVE,
        live_confirmation="wrong",
    )

    assert [violation.code for violation in check_all(bundle)] == ["C-21"]


def test_non_dry_run_requires_exactly_one_enabled_general_account() -> None:
    bundle = _app_update(_bundle(), ("run",), env=ExecEnv.PAPER)

    assert [violation.code for violation in check_all(bundle)] == ["C-22"]


def test_upbit_broker_and_account_type_must_be_biconditional() -> None:
    bundle = _app_update(
        _bundle(),
        (),
        accounts=(_account(account_type="upbit", broker="KIS"),),
    )

    assert [violation.code for violation in check_all(bundle)] == ["C-22"]


def test_fraction_restore_mode_rejects_destination_rho() -> None:
    bundle = _app_update(_bundle(), ("band",), restore_rho=Decimal("0.9"))

    assert [violation.code for violation in check_all(bundle)] == ["C-31"]
