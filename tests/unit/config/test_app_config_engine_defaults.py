"""Canonical defaults for engine, execution, and backtest blocks."""

from collections.abc import Mapping
from decimal import Decimal

from omra.config import AppConfig

_ENGINE_ROOTS = (
    "risk",
    "core",
    "satellite",
    "cash",
    "bl",
    "mvo",
    "cov",
    "sanity",
    "band",
    "rebalance",
    "universe",
    "trade",
    "momentum",
    "crypto",
    "mc",
    "gk",
    "backtest",
    "order",
    "execution",
    "etf",
)


def _config() -> AppConfig:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {}}
    return AppConfig.model_validate(values)


def _contains_float(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(item) for item in value)
    return isinstance(value, float)


def test_engine_execution_and_backtest_defaults_match_the_canonical_tables() -> None:
    dump = _config().model_dump(mode="json")
    actual = {root: dump[root] for root in _ENGINE_ROOTS}

    assert actual == {
        "risk": {"level": 6},
        "core": {"min_weight": "0.80"},
        "satellite": {
            "total_cap": "0.20",
            "momentum": {
                "enabled": False,
                "cap": "0.10",
                "pair": ["VOO", "VXUS"],
                "return_basis": "usd_total_return",
                "dd_basis": "sleeve_krw_peak_to_trough",
                "turnover_cap_annual": "2.00",
            },
        },
        "cash": {"buffer": "0.01", "frozen_reserve_alert_pct": "0.05"},
        "bl": {
            "tau": "0.025",
            "delta_mkt": "3.0",
            "max_views": 3,
            "view_shift_cap": "0.015",
        },
        "mvo": {
            "lambda_risk_bounds": ["0.5", "30"],
            "turnover_gamma": "0.01",
            "asset_cap": "0.40",
            "asset_cap_overrides": {"nasdaq": "0.10", "reits": "0.05"},
        },
        "cov": {
            "strategic": "lw_constant_correlation",
            "lookback_days": 756,
            "monitor": {"lam": "0.94", "days": 60},
            "condition_number_max": 1_000,
        },
        "sanity": {"hrp_divergence": "0.20"},
        "band": {
            "abs": "0.05",
            "rel": "0.25",
            "pension_scheduled_abs": "0.07",
            "pension_scheduled_rel": "0.35",
            "isa_abs": "0.07",
            "isa_rel": "0.35",
            "crypto_abs": "0.01",
            "crypto_rel": "0.30",
            "class_abs": "0.05",
            "restore_fraction": "0.5",
            "restore_mode": "fraction",
            "restore_rho": None,
        },
        "rebalance": {"cooldown_days": 5},
        "universe": {"shrink_below_krw": 30_000_000, "restore_above_krw": 40_000_000},
        "trade": {"min_amount": {"kr": "50000", "us": "100", "upbit": "10000"}},
        "momentum": {"lookbacks": [3, 6, 9, 12]},
        "crypto": {
            "enabled": False,
            "target": "0.03",
            "cap": "0.10",
            "mix": {"KRW-BTC": "0.70", "KRW-ETH": "0.30"},
            "vol_target": "0.40",
            "vol_scale_floor": "0.33",
            "kimchi_halt": "0.08",
            "kimchi_alert": "0.05",
            "drop_guard_24h_pct": "-0.15",
            "vol_scale_max_age_days": 10,
        },
        "mc": {
            "paths": 5_000,
            "block": 6,
            "success_bands": {"green": "0.75", "amber": "0.60"},
            "cost_annual": "0.0035",
            "inflation_annual": "0.02",
        },
        "gk": {"guardrail": "0.20", "adjust": "0.10"},
        "backtest": {
            "account_model": "single",
            "gates": {
                "core": "WF(5+1y) + lookahead 0건 + 스냅샷 회귀(config 포함)",
                "satellite": "CPCV(21/5) + 이웃 ±25% + DSR>0.95 + 부트스트랩",
                "challenger_years": 10,
            },
            "sim_mode": "clean",
            "costs": {
                "fee_kr": "0.00015",
                "fee_us": "0.0009",
                "fee_crypto": "0.0005",
                "tax_sell_kr_stock": "0.0015",
                "slip_kr_etf_bp": "5",
                "slip_us_bp": "3",
                "slip_crypto_bp": "10",
                "fx_spread_roundtrip": "0.002",
            },
            "data": {"max_gap_pct": "0.5"},
            "lookahead": {"samples": 10, "weight_tolerance": "1E-9"},
            "snapshot": {"tolerance_pct": None, "absolute_floor": None},
            "benchmark": {
                "composition": {"equity": "0.60", "bond": "0.40"},
                "rebalance": "annual",
                "apply_costs": True,
                "track": "pretax",
            },
            "tax": {"harvest_enabled": True},
            "seed": 20_260_101,
            "us_fill_basis": "close",
        },
        "order": {
            "max_amount_krw": 5_000_000,
            "reprice": {"interval_min": 5, "max_count": 3},
            "us_strategy": "loc",
        },
        "execution": {"max_open_orders": {"kis_domestic": 6, "kis_overseas": 6, "upbit": 4}},
        "etf": {
            "premium_gate": {
                "threshold_pct": "0.5",
                "threshold_ticks": 3,
                "rest_defer_minutes": 30,
                "max_defer_count": 3,
                "min_wait_sec": 300,
                "max_total_defer_min": 90,
            }
        },
    }


def test_engine_decimal_fields_materialize_as_decimal_not_float() -> None:
    config = _config()

    assert isinstance(config.core.min_weight, Decimal)
    assert isinstance(config.backtest.lookahead.weight_tolerance, Decimal)
    assert isinstance(config.etf.premium_gate.threshold_pct, Decimal)
    assert not _contains_float(config.model_dump())
