"""Canonical defaults for improvement, policy, and operations blocks."""

from omra.config import AppConfig

_POLICY_OPS_ROOTS = (
    "run",
    "accounts",
    "research",
    "labs",
    "policy",
    "canary",
    "data",
    "watchdog",
    "runtime",
    "tools",
    "web",
    "secrets",
    "jobs",
    "monitoring",
)


def _dump() -> dict[str, object]:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {}}
    dump = AppConfig.model_validate(values).model_dump(mode="json")
    return {root: dump[root] for root in _POLICY_OPS_ROOTS}


def test_policy_improvement_and_operations_defaults_match_canonical_tables() -> None:
    assert _dump() == {
        "run": {
            "env": "dry_run",
            "live_confirmation": None,
            "manual_approve": False,
            "max_account_value": None,
            "kill_file": "/app/var/data/KILL",
        },
        "accounts": [],
        "research": {
            "enabled": False,
            "collect_cron": "0 4 * * 0",
            "digest_cron": "0 5 1 * *",
            "max_items_per_digest": 40,
            "max_chars_per_item": 8_000,
            "source_fail_streak_warn": 3,
            "citation_fail_rate_alert": "0.10",
            "sources": {
                "github_releases": {"enabled": True, "priority": "P0"},
                "pypi_json": {"enabled": True, "priority": "P0"},
                "kis_repo": {"enabled": True, "priority": "P0"},
                "kr_tax_notice": {"enabled": True, "priority": "P0"},
                "upbit_docs": {"enabled": True, "priority": "P1"},
                "arxiv_qfin": {"enabled": True, "priority": "P1"},
                "practitioner_rss": {"enabled": True, "priority": "P1"},
                "skfolio_docs": {"enabled": False, "priority": "P2"},
            },
            "llm": {
                "model": "claude-opus-5",
                "effort": "low",
                "max_output_tokens": 4_096,
                "use_batch": True,
                "monthly_budget_usd": {"research_extract": "0"},
            },
            "user_agent": "omra-research/1.0 (+self-hosted; contact via operator)",
            "inbox_root": "/app/var/data/research/inbox",
            "report_root": "/app/var/reports/research",
        },
        "labs": {
            "enabled": False,
            "challenger_enabled": False,
            "tuning_space": [],
            "shadow_min_days": 126,
            "g2": {"mode": "full"},
            "canary": {
                "targets_recalc": {
                    "alphas": ["0.333", "0.667", "1.0"],
                    "days_per_step": 5,
                },
                "method_swap": {
                    "alphas": ["0.25", "0.50", "1.0"],
                    "days_per_step": 20,
                },
                "universe_swap": {
                    "alphas": ["0.5", "1.0"],
                    "days_per_step": 10,
                },
                "veto_window_hours": 72,
            },
            "rollback": {
                "r1_te_residual_pp": "0.3",
                "r1_breach_count": 2,
                "r2_guard_multiple": "2.0",
                "r3_turnover_multiple": "1.3",
                "r3_budget_consumption": "0.8",
                "r4_exec_failure_multiple": "2.0",
                "freeze_days_after_2_rollbacks": 90,
                "annual_rollback_alarm": 3,
            },
        },
        "policy": {
            "change_budget": {
                "total_per_year": 6,
                "targets_per_year": 4,
                "params_per_year": 4,
                "logic_per_year": 2,
            },
            "auto_threshold_pp": "8",
            "reject_threshold_pp": "20",
            "auto_nocanary_threshold_pp": "3",
        },
        "canary": {
            "targets": {"alphas": ["0.333", "0.667", "1.0"], "days_per_step": 5},
            "methodology": {
                "alphas": ["0.25", "0.50", "1.0"],
                "days_per_step": 20,
            },
        },
        "data": {
            "quality": {
                "max_abs_daily_return": "0.3",
                "max_abs_daily_return_crypto": "0.5",
            },
            "master": {"files": ["kospi_code.mst.zip", "kosdaq_code.mst.zip"]},
            "providers": {},
        },
        "watchdog": {
            "interval_sec": 10,
            "heartbeat_max_age_sec": 180,
            "loop_lag_exit_ms": 5_000,
            "consecutive": 3,
            "crashloop_window_min": 10,
            "crashloop_max": 3,
        },
        "runtime": {"role": "app", "fill_queue_warn": 1_000},
        "tools": {"snapshot_max_age_h": 168},
        "web": {
            "bind_host": "0.0.0.0",  # noqa: S104 - canonical default under contract
            "bind_port": 8_080,
            "public_exposed": False,
            "https": False,
            "session_idle_hours": 12,
            "session_max_days": 30,
            "request_budget_ms": 2_000,
            "shutdown_grace_sec": 5,
        },
        "secrets": {
            "ladder_days": [45, 30, 14, 7, 3, 1],
            "issue_spacing_days": 180,
        },
        "jobs": {
            "overrides": {},
            "planner": {
                "steps": {
                    "token_refresh_sec": 30,
                    "approval_key_sec": 60,
                    "calendar_crosscheck_sec": 30,
                    "fx_snapshot_sec": 30,
                    "inflow_waterfall_sec": 45,
                    "secret_expiry_sec": 5,
                    "presence_ladder_sec": 5,
                    "health_snapshot_sec": 10,
                    "register_dynamic_sec": 5,
                    "labs_canary_eval_sec": 5,
                    "surveillance_sec": 300,
                }
            },
            "us_submit_lead": 10,
            "catchup": {"serial": True},
            "dep_wait": {"universe_reeval_min": 30, "master_diff_min": 30},
        },
        "monitoring": {
            "heartbeat_interval_sec": 30,
            "disk": {"warn_pct": 80, "block_pct": 90, "release_pct": 85},
            "logs": {
                "retention_days": 14,
                "retention_days_pressure": 7,
                "research_inbox_retention_months": 13,
            },
            "dms": {"ping_url": None, "ping_interval_min": 15},
            "health": {"thresholds": {}},
        },
    }
