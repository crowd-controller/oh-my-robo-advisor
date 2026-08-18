"""Canonical defaults for tax, safety, and observation blocks."""

from omra.config import AppConfig

_SAFETY_ROOTS = (
    "tax",
    "waterfall",
    "protections",
    "safe_mode",
    "presence",
    "tracking_error",
    "alerts",
    "ws",
    "quote",
    "fx",
    "guard",
    "realtime",
    "surveillance",
)


def _dump() -> dict[str, object]:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {}}
    dump = AppConfig.model_validate(values).model_dump(mode="json")
    return {root: dump[root] for root in _SAFETY_ROOTS}


def test_tax_safety_and_observation_defaults_match_the_canonical_tables() -> None:
    assert _dump() == {
        "tax": {
            "harvest_start": "11-25",
            "deduction": 2_500_000,
            "income_alerts": {
                "api": {
                    "health": 10_000_000,
                    "info": 12_000_000,
                    "warn": 16_000_000,
                    "soft_stop": 18_000_000,
                },
                "fallback": {
                    "health": 10_000_000,
                    "info": 14_000_000,
                    "warn": 18_000_000,
                    "soft_stop": 19_000_000,
                },
            },
            "basis_price_source": "fallback",
            "isa_free_limit": 2_000_000,
            "isa_usage_alert": "0.70",
            "isa_contract_start_date": None,
            "isa_usage_opening_amount": None,
            "isa_usage_opening_as_of": None,
            "harvest_rebuy_buffer_pct": "0.005",
            "health_insurance_status": "regional",
            "user_marginal_credit_rate": "0.132",
            "crypto_tax_enabled": False,
            "harvest_auto_enabled": False,
        },
        "waterfall": {
            "fill_pension_to_limit": False,
            "pension_deduct_cap_total": 9_000_000,
            "pension_deduct_cap_savings": 6_000_000,
            "gap_check_date": "11-01",
            "reminders": ["12-08", "12-15", "12-19"],
            "transfer_reserve_expiry_days": 7,
        },
        "protections": {
            "mdd_safe_mode_pct": "-15",
            "mdd_halt_pct": "-25",
            "mdd_recover_pct": "-10",
            "mdd_recover_days": 5,
            "daily_order_count": 30,
            "daily_order_amount_pct": "30",
            "daily_order_amount_abs_krw": None,
            "symbol_cooldown_hits": 3,
            "symbol_cooldown_hours": 24,
            "symbol_cooldown_window_min": 60,
            "price_outlier_pct": "15",
            "price_outlier_pct_crypto": "30",
            "quote_stale_min": 5,
            "spread_max_pct": "1.0",
            "reconcile_tolerance_shares": 0,
            "reconcile_tolerance_cash_krw": None,
            "error_streak_order": 5,
            "error_streak_quote": 5,
            "turnover_monthly_mult_warn": "2",
            "turnover_monthly_mult_halt": "3",
            "turnover_annual_assumption": "0.30",
            "turnover_carryover_cap_days": 60,
            "turnover_streak_safe_mode": 3,
            "surveillance_stale_hours": 24,
            "frozen_nav_safe_mode_pct": "20",
            "frozen_nav_halt_pct": "40",
            "deadline_pause_days": 3,
            "event_burst_abs": 4,
            "event_burst_ratio": "0.30",
        },
        "safe_mode": {
            "net_buy_daily_cap_pct": "3",
            "net_buy_monthly_cap_pct": "10",
            "net_buy_monthly_window_days": 30,
            "order_size_divisor": 3,
            "band_multiplier": "2",
        },
        "presence": {
            "away_soft_h": 24,
            "away_h": 72,
            "away_long_d": 7,
            "grace_normal_min": 30,
            "grace_away_soft_h": 4,
            "grace_away_h": 12,
            "halt_downgrade_no_response_h": 24,
            "grace_cap_kst": {"crypto": "08:55", "krx": "09:45", "us_loc": "-PT30M"},
        },
        "tracking_error": {"residual_monthly_threshold_pp": "0.3"},
        "alerts": {
            "guard_verdict_default": "silent",
            "surveillance_state_entry": "info",
            "critical_channels": ["telegram", "smtp"],
            "both_channels_fail_safe_mode_days": 2,
            "info_immediate_max_per_day": 5,
        },
        "ws": {
            "tier1_execution_window_only": True,
            "tier1_enabled": False,
            "subscription_cap": 38,
            "reserve": 3,
            "max_active_symbols": 9,
        },
        "quote": {"max_age_ms": {"krx": 2_000, "upbit": 2_000, "us": None}},
        "fx": {"max_age_hours": 72},
        "guard": {
            "oneway": True,
            "min_duration_sec": 30,
            "move_guard": {
                "window_sec": 300,
                "nav_weighted_move_pct": "3.0",
                "min_symbols": 2,
                "min_samples": 5,
            },
        },
        "realtime": {"rest_fallback_poll_sec": 30, "upbit_maintenance_fail_streak": 3},
        "surveillance": {
            "max_age_trading_days": 2,
            "unknown_default_level": "SV2",
            "override_max_days": 90,
            "override_clear_max_days": 30,
            "daily_poll_timeout_sec": 300,
            "sources": {
                "kis_master": {
                    "enabled": True,
                    "grade": "official",
                    "max_auto_level": "SV3",
                    "max_age_trading_days": None,
                    "max_age_hours": None,
                },
                "kis_stock_info": {
                    "enabled": True,
                    "grade": "official",
                    "max_auto_level": "SV3",
                    "max_age_trading_days": None,
                    "max_age_hours": None,
                },
                "kis_ksdinfo": {
                    "enabled": True,
                    "grade": "official",
                    "max_auto_level": "SV3",
                    "max_age_trading_days": None,
                    "max_age_hours": None,
                },
                "kis_overseas": {
                    "enabled": False,
                    "grade": "official",
                    "max_auto_level": "SV3",
                    "max_age_trading_days": None,
                    "max_age_hours": None,
                },
                "upbit_market": {
                    "enabled": False,
                    "grade": "official",
                    "max_auto_level": "SV3",
                    "max_age_trading_days": None,
                    "max_age_hours": 12,
                },
                "kis_ws_market": {
                    "enabled": False,
                    "grade": "official",
                    "max_auto_level": "SV3",
                    "max_age_trading_days": None,
                    "max_age_hours": None,
                },
            },
        },
    }
