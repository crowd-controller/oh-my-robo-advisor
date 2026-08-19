"""Canonical SQLite table and index catalog tests."""

from typing import Final

from sqlalchemy.dialects import sqlite

from omra.persistence.models import TABLE_NAMES, Base

_EXPECTED_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "approval_requests": (
        "id",
        "kind",
        "subject_key",
        "account_id",
        "payload_json",
        "requested_at",
        "grace_deadline",
        "timeout_action",
        "state",
        "decided_at",
        "decided_by",
        "created_at",
    ),
    "bot_state": ("id", "state", "safe_mode_reasons", "since", "prev_state"),
    "broker_tokens": (
        "broker",
        "env",
        "credential_id",
        "kind",
        "token",
        "issued_at",
        "expires_at",
        "updated_at",
    ),
    "canary_state": (
        "change_id",
        "target_kind",
        "ladder_json",
        "step_index",
        "alpha_current",
        "step_started_on",
        "w_champion_ref",
        "state",
        "veto_deadline",
        "created_at",
        "updated_at",
    ),
    "change_budget": ("year", "bucket", "cap", "consumed", "updated_at"),
    "contribution_ledger": (
        "account_id",
        "year",
        "ytd_paid_krw",
        "source",
        "as_of",
        "updated_at",
    ),
    "execution_state": (
        "run_date",
        "venue",
        "instrument_key",
        "counter_kind",
        "value",
        "updated_at",
    ),
    "experiment_events": ("id", "experiment_id", "event_kind", "payload_json", "created_at"),
    "experiments": (
        "experiment_id",
        "spec_hash",
        "hypothesis",
        "primary_metric",
        "secondary_metrics",
        "stop_conditions",
        "sample_from",
        "sample_to",
        "registered_at",
        "registered_by",
        "payload_json",
    ),
    "fills": (
        "id",
        "order_id",
        "qty",
        "price",
        "fee",
        "tax",
        "filled_at_kst",
        "settle_date",
        "broker_exec_id",
    ),
    "harvest_ledger": (
        "year",
        "order_amount_krw_cum",
        "realized_target_krw_cum",
        "updated_at",
    ),
    "market_holidays": ("venue", "cal_date", "source", "is_open", "session_note", "fetched_at"),
    "nav_snapshots": (
        "snap_date",
        "account_id",
        "nav_krw",
        "cash_krw",
        "positions_json",
        "fx_usdkrw",
        "frozen_reserve_krw",
        "created_at",
    ),
    "notification_suppression": (
        "subject_key",
        "reason_key",
        "last_sent_date",
        "last_sent_at",
        "send_count",
        "updated_at",
    ),
    "orders": (
        "id",
        "account_id",
        "broker_order_id",
        "broker_order_org_no",
        "orig_broker_order_id",
        "instrument_key",
        "side",
        "order_type",
        "intent",
        "qty",
        "limit_price",
        "status",
        "plan_id",
        "reprice_count",
        "submitted_at_kst",
        "dry_run",
    ),
    "pending_tax_events": (
        "id",
        "instrument_key",
        "risk_type",
        "abol_date",
        "cross_checked",
        "observed_at",
        "state",
    ),
    "pending_transfers": (
        "account_id",
        "instrument_key",
        "abol_date",
        "substitute_key",
        "total_qty",
        "slices_total",
        "slices_done",
        "state",
        "created_at",
    ),
    "policy_versions": ("kind", "version", "as_of", "inputs_hash", "path"),
    "portfolio_decomposition": (
        "version",
        "account_id",
        "instrument_key",
        "sub_alloc_krw",
        "is_legacy",
    ),
    "portfolio_decomposition_meta": (
        "version",
        "as_of",
        "v_total_at_save",
        "v_a_at_save_json",
        "targets_capped_json",
        "targets_version",
        "trigger",
        "created_at",
    ),
    "positions": ("account_id", "instrument_key", "qty", "avg_cost", "updated_at"),
    "presence": ("id", "state", "last_seen_at", "declared_away", "away_until", "since"),
    "protection_counters": (
        "breaker_id",
        "run_date",
        "scope_key",
        "counter_kind",
        "value",
        "updated_at",
    ),
    "protection_state": (
        "breaker_id",
        "scope_key",
        "status",
        "grade",
        "tripped_at",
        "cleared_at",
        "reason_json",
        "counters_json",
        "updated_at",
    ),
    "rebalance_plans": (
        "id",
        "as_of_kst",
        "reason",
        "sleeve_id",
        "expected_turnover",
        "sanity_json",
        "approved",
        "approved_at",
        "rejected_at",
        "targets_version",
        "universe_version",
        "inputs_hash",
        "payload_json",
        "created_at",
    ),
    "reconcile_expectations": (
        "id",
        "account_id",
        "kind",
        "instrument_key",
        "expected_date_from",
        "expected_date_to",
        "expected_qty",
        "expected_amount",
        "amount_tolerance",
        "source",
        "consumed_at",
        "expires_at",
        "created_at",
    ),
    "research_extractions": (
        "id",
        "payload_hash",
        "source_url",
        "source_grade",
        "published_at",
        "title",
        "claim",
        "layer",
        "decay_type",
        "affected_docs",
        "affected_params",
        "quoted_numbers",
        "flags",
        "conflicts_with_ours",
        "verdict",
        "reject_rule",
        "collected_at",
    ),
    "run_ledger": (
        "run_date",
        "venue",
        "task_name",
        "status",
        "started_at",
        "finished_at",
        "note",
    ),
    "satellite_state": (
        "sub_sleeve_id",
        "lookback_months",
        "current_holding_key",
        "stage_pct",
        "last_eval_date",
        "peak_krw",
        "dd_stage",
        "dd_entered_at",
        "cooldown_until",
        "carryover_pct",
        "ytd_turnover_pct",
        "updated_at",
    ),
    "sleeve_state": ("sleeve_id", "state", "reason", "since"),
    "surveillance_flags": (
        "instrument_key",
        "risk_type",
        "source",
        "level",
        "state",
        "raw_value",
        "observed_at",
        "effective_from",
        "resolved_at",
        "deadline_at",
        "override_level",
        "override_expires_at",
        "override_actor",
        "override_reason",
    ),
    "tax_events": (
        "id",
        "account_id",
        "instrument_key",
        "kind",
        "amount_krw",
        "qty",
        "settle_date",
        "fx_rate",
        "source",
        "fill_id",
        "created_at",
    ),
    "taxbase_snapshots": ("instrument_key", "as_of", "taxbase_price", "source", "fetched_at"),
    "unmatched_fills": (
        "id",
        "account_id",
        "instrument_key",
        "side",
        "qty",
        "price",
        "filled_at_kst",
        "broker_exec_id",
        "raw_json",
        "state",
        "resolved_at",
        "resolution",
        "observed_at",
    ),
}

_EXPECTED_INDEXES: Final[frozenset[str]] = frozenset(
    {
        "ix_approvals_open",
        "ix_decomp_meta_asof",
        "ix_experiments_hash",
        "ix_expev_exp",
        "ix_fills_order",
        "ix_fills_settle",
        "ix_orders_intent",
        "ix_orders_netbuy",
        "ix_orders_open",
        "ix_orders_orphan",
        "ix_orders_plan",
        "ix_plans_asof",
        "ix_prot_tripped",
        "ix_reconcile_open",
        "ix_research_verdict",
        "ix_survflags_active",
        "ix_taxev_year",
        "ix_unmatched_open",
        "ux_reconcile_idem",
    }
)


def test_schema_has_the_complete_canonical_table_and_column_catalog() -> None:
    actual = {
        name: tuple(column.name for column in table.columns)
        for name, table in sorted(Base.metadata.tables.items())
    }

    assert len(actual) == 34
    assert frozenset(_EXPECTED_COLUMNS) == TABLE_NAMES
    assert actual == _EXPECTED_COLUMNS


def test_sqlite_schema_uses_only_integer_and_lossless_text_storage() -> None:
    dialect = sqlite.dialect()
    storage_types = {
        column.type.compile(dialect=dialect).upper()
        for table in Base.metadata.tables.values()
        for column in table.columns
    }

    assert storage_types == {"INTEGER", "TEXT"}


def test_schema_has_the_complete_named_index_catalog() -> None:
    actual = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.name is not None
    }

    assert actual == _EXPECTED_INDEXES


def test_experiment_g0_fields_remain_nullable_and_legacy_counter_is_absent() -> None:
    experiments = Base.metadata.tables["experiments"]

    assert all(
        experiments.columns[name].nullable
        for name in ("hypothesis", "primary_metric", "secondary_metrics", "stop_conditions")
    )
    assert "n_specs_tried_to_date" not in experiments.columns
