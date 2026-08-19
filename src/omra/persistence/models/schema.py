"""SQLAlchemy metadata for the complete transactional SQLite schema."""

from datetime import datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from omra.persistence.types import DecimalText, KSTDateTimeText

NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with stable Alembic constraint names."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class OrderRow(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("broker_order_id", "account_id"),
        Index(
            "ix_orders_open",
            "account_id",
            "status",
            sqlite_where=text("status IN ('SUBMITTING','PENDING','PARTIALLY_FILLED')"),
        ),
        Index("ix_orders_intent", "intent", "submitted_at_kst"),
        Index("ix_orders_netbuy", "submitted_at_kst", "side", "status"),
        Index(
            "ix_orders_orphan",
            "account_id",
            "instrument_key",
            "side",
            "submitted_at_kst",
            sqlite_where=text("status IN ('SUBMITTING','EXPIRED_UNKNOWN')"),
        ),
        Index("ix_orders_plan", "plan_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(Text)
    broker_order_org_no: Mapped[str | None] = mapped_column(Text)
    orig_broker_order_id: Mapped[str | None] = mapped_column(Text)
    instrument_key: Mapped[str] = mapped_column(Text, nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)
    order_type: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(DecimalText())
    status: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(Text)
    reprice_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    submitted_at_kst: Mapped[datetime | None] = mapped_column(KSTDateTimeText())
    dry_run: Mapped[int] = mapped_column(Integer, nullable=False)


class FillRow(Base):
    __tablename__ = "fills"
    __table_args__ = (
        UniqueConstraint("broker_exec_id"),
        Index("ix_fills_order", "order_id"),
        Index("ix_fills_settle", "settle_date"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    qty: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    price: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    fee: Mapped[Decimal | None] = mapped_column(DecimalText())
    tax: Mapped[Decimal | None] = mapped_column(DecimalText())
    filled_at_kst: Mapped[datetime] = mapped_column(KSTDateTimeText(), nullable=False)
    settle_date: Mapped[str] = mapped_column(Text, nullable=False)
    broker_exec_id: Mapped[str | None] = mapped_column(Text)


class PositionRow(Base):
    __tablename__ = "positions"

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(Text, primary_key=True)
    qty: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class RunLedgerRow(Base):
    __tablename__ = "run_ledger"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','done','skipped','failed')",
            name="status_values",
        ),
    )

    run_date: Mapped[str] = mapped_column(Text, primary_key=True)
    venue: Mapped[str] = mapped_column(Text, primary_key=True)
    task_name: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class BotStateRow(Base):
    __tablename__ = "bot_state"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    safe_mode_reasons: Mapped[str | None] = mapped_column(Text)
    since: Mapped[str] = mapped_column(Text, nullable=False)
    prev_state: Mapped[str | None] = mapped_column(Text)


class SleeveStateRow(Base):
    __tablename__ = "sleeve_state"

    sleeve_id: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    since: Mapped[str] = mapped_column(Text, nullable=False)


class PolicyVersionRow(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (CheckConstraint("kind IN ('targets','universe')", name="kind_values"),)

    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)


class ReconcileExpectationRow(Base):
    __tablename__ = "reconcile_expectations"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('cash_in','cash_out','fill','scheduled_fill','ca_qty','fx_resettle',"
            "'orphan_order')",
            name="kind_values",
        ),
        CheckConstraint("amount_tolerance > 0", name="positive_tolerance"),
        CheckConstraint(
            "source IN ('external_schedule','master_diff','ksdinfo','broker_fx',"
            "'broker_dividend','system','instruction')",
            name="source_values",
        ),
        Index(
            "ux_reconcile_idem",
            "source",
            "account_id",
            "kind",
            text("ifnull(instrument_key,'')"),
            "expected_date_from",
            unique=True,
        ),
        Index(
            "ix_reconcile_open",
            "account_id",
            "kind",
            "expected_date_from",
            sqlite_where=text("consumed_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_key: Mapped[str | None] = mapped_column(Text)
    expected_date_from: Mapped[str] = mapped_column(Text, nullable=False)
    expected_date_to: Mapped[str] = mapped_column(Text, nullable=False)
    expected_qty: Mapped[int | None] = mapped_column(Integer)
    expected_amount: Mapped[int | None] = mapped_column(Integer)
    amount_tolerance: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    consumed_at: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class SurveillanceFlagRow(Base):
    __tablename__ = "surveillance_flags"
    __table_args__ = (
        CheckConstraint(
            "state IN ('ACTIVE','RESOLVED','UNRESOLVED','FALSE_POSITIVE')",
            name="state_values",
        ),
        Index("ix_survflags_active", "instrument_key", "state", "effective_from"),
    )

    instrument_key: Mapped[str] = mapped_column(Text, primary_key=True)
    risk_type: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(Text)
    deadline_at: Mapped[str | None] = mapped_column(Text)
    override_level: Mapped[int | None] = mapped_column(Integer)
    override_expires_at: Mapped[str | None] = mapped_column(Text)
    override_actor: Mapped[str | None] = mapped_column(Text)
    override_reason: Mapped[str | None] = mapped_column(Text)


class PendingTransferRow(Base):
    __tablename__ = "pending_transfers"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING','RUNNING','DONE','ABORTED')", name="state_values"),
    )

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(Text, primary_key=True)
    abol_date: Mapped[str] = mapped_column(Text, nullable=False)
    substitute_key: Mapped[str] = mapped_column(Text, nullable=False)
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    slices_total: Mapped[int] = mapped_column(Integer, nullable=False)
    slices_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    state: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class BrokerTokenRow(Base):
    __tablename__ = "broker_tokens"
    __table_args__ = (
        CheckConstraint("broker IN ('kis','upbit')", name="broker_values"),
        CheckConstraint("env IN ('live','paper')", name="env_values"),
        CheckConstraint("kind IN ('access_token','approval_key')", name="kind_values"),
    )

    broker: Mapped[str] = mapped_column(Text, primary_key=True)
    env: Mapped[str] = mapped_column(Text, primary_key=True)
    credential_id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, server_default=text("'*'")
    )
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class PendingTaxEventRow(Base):
    __tablename__ = "pending_tax_events"
    __table_args__ = (
        CheckConstraint("state IN ('OPEN','CONSUMED','EXPIRED')", name="state_values"),
        UniqueConstraint("instrument_key", "risk_type", "abol_date"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(Text, nullable=False)
    risk_type: Mapped[str] = mapped_column(Text, nullable=False)
    abol_date: Mapped[str] = mapped_column(Text, nullable=False)
    cross_checked: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)


class RebalancePlanRow(Base):
    __tablename__ = "rebalance_plans"
    __table_args__ = (Index("ix_plans_asof", "as_of_kst"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of_kst: Mapped[datetime] = mapped_column(KSTDateTimeText(), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    sleeve_id: Mapped[str | None] = mapped_column(Text)
    expected_turnover: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    sanity_json: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    approved_at: Mapped[str | None] = mapped_column(Text)
    rejected_at: Mapped[str | None] = mapped_column(Text)
    targets_version: Mapped[int | None] = mapped_column(Integer)
    universe_version: Mapped[int | None] = mapped_column(Integer)
    inputs_hash: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class ExecutionStateRow(Base):
    __tablename__ = "execution_state"

    run_date: Mapped[str] = mapped_column(Text, primary_key=True)
    venue: Mapped[str] = mapped_column(Text, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, server_default=text("'*'")
    )
    counter_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class PresenceRow(Base):
    __tablename__ = "presence"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("state IN ('NORMAL','AWAY_SOFT','AWAY','AWAY_LONG')", name="state_values"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[str] = mapped_column(Text, nullable=False)
    declared_away: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    away_until: Mapped[str | None] = mapped_column(Text)
    since: Mapped[str] = mapped_column(Text, nullable=False)


class MarketHolidayRow(Base):
    __tablename__ = "market_holidays"
    __table_args__ = (
        CheckConstraint("source IN ('exchange_calendars','kis_tr')", name="source_values"),
    )

    venue: Mapped[str] = mapped_column(Text, primary_key=True)
    cal_date: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    is_open: Mapped[int] = mapped_column(Integer, nullable=False)
    session_note: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False)


class NavSnapshotRow(Base):
    __tablename__ = "nav_snapshots"

    snap_date: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    nav_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    positions_json: Mapped[str] = mapped_column(Text, nullable=False)
    fx_usdkrw: Mapped[Decimal | None] = mapped_column(DecimalText())
    frozen_reserve_krw: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class TaxEventRow(Base):
    __tablename__ = "tax_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('realized_pnl','dividend','distribution','interest','withholding',"
            "'redemption')",
            name="kind_values",
        ),
        CheckConstraint(
            "source IN ('broker_032','period_rights','computed','manual')",
            name="source_values",
        ),
        Index("ix_taxev_year", "account_id", "settle_date", "kind"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_key: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    amount_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal | None] = mapped_column(DecimalText())
    settle_date: Mapped[str] = mapped_column(Text, nullable=False)
    fx_rate: Mapped[Decimal | None] = mapped_column(DecimalText())
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fill_id: Mapped[str | None] = mapped_column(ForeignKey("fills.id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class TaxbaseSnapshotRow(Base):
    __tablename__ = "taxbase_snapshots"

    instrument_key: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of: Mapped[str] = mapped_column(Text, primary_key=True)
    taxbase_price: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False)


class ContributionLedgerRow(Base):
    __tablename__ = "contribution_ledger"
    __table_args__ = (CheckConstraint("source IN ('api','csv','manual')", name="source_values"),)

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    ytd_paid_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    as_of: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class HarvestLedgerRow(Base):
    __tablename__ = "harvest_ledger"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_amount_krw_cum: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    realized_target_krw_cum: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class ApprovalRequestRow(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','APPROVED','REJECTED','EXPIRED','ESCALATED','CANCELLED')",
            name="state_values",
        ),
        Index(
            "ix_approvals_open",
            "state",
            "grace_deadline",
            sqlite_where=text("state = 'PENDING'"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    subject_key: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[str] = mapped_column(Text, nullable=False)
    grace_deadline: Mapped[str | None] = mapped_column(Text)
    timeout_action: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class CanaryStateRow(Base):
    __tablename__ = "canary_state"
    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('targets','methodology','universe_swap')",
            name="target_kind_values",
        ),
        CheckConstraint("state IN ('ACTIVE','DONE','ROLLED_BACK')", name="state_values"),
    )

    change_id: Mapped[str] = mapped_column(Text, primary_key=True)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    ladder_json: Mapped[str] = mapped_column(Text, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alpha_current: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    step_started_on: Mapped[str] = mapped_column(Text, nullable=False)
    w_champion_ref: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    veto_deadline: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class ChangeBudgetRow(Base):
    __tablename__ = "change_budget"
    __table_args__ = (
        CheckConstraint("bucket IN ('total','targets','params','logic')", name="bucket_values"),
    )

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket: Mapped[str] = mapped_column(Text, primary_key=True)
    cap: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class ExperimentRow(Base):
    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_hash", "spec_hash"),)

    experiment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    spec_hash: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    primary_metric: Mapped[str | None] = mapped_column(Text)
    secondary_metrics: Mapped[str | None] = mapped_column(Text)
    stop_conditions: Mapped[str | None] = mapped_column(Text)
    sample_from: Mapped[str] = mapped_column(Text, nullable=False)
    sample_to: Mapped[str] = mapped_column(Text, nullable=False)
    registered_at: Mapped[str] = mapped_column(Text, nullable=False)
    registered_by: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class ExperimentEventRow(Base):
    __tablename__ = "experiment_events"
    __table_args__ = (
        CheckConstraint(
            "event_kind IN ('registered','run_started','run_finished','gate_passed',"
            "'gate_failed','promoted','rolled_back','frozen')",
            name="event_kind_values",
        ),
        Index("ix_expev_exp", "experiment_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.experiment_id"), nullable=False
    )
    event_kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchExtractionRow(Base):
    __tablename__ = "research_extractions"
    __table_args__ = (
        CheckConstraint(
            "source_grade IN ('official','vendor','preprint','blog')",
            name="source_grade_values",
        ),
        CheckConstraint("layer IN ('T0','T1','T2','T3')", name="layer_values"),
        CheckConstraint("decay_type IN ('dep','api','law','evidence')", name="decay_type_values"),
        CheckConstraint("verdict IN ('REVIEW','REJECT')", name="verdict_values"),
        UniqueConstraint("payload_hash"),
        Index("ix_research_verdict", "verdict", "collected_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_grade: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str] = mapped_column(Text, nullable=False)
    decay_type: Mapped[str | None] = mapped_column(Text)
    affected_docs: Mapped[str] = mapped_column(Text, nullable=False)
    affected_params: Mapped[str] = mapped_column(Text, nullable=False)
    quoted_numbers: Mapped[str] = mapped_column(Text, nullable=False)
    flags: Mapped[str] = mapped_column(Text, nullable=False)
    conflicts_with_ours: Mapped[str | None] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    reject_rule: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)


class ProtectionStateRow(Base):
    __tablename__ = "protection_state"
    __table_args__ = (
        CheckConstraint("status IN ('ARMED','TRIPPED')", name="status_values"),
        CheckConstraint("grade IN ('A','B','B_STAR','C')", name="grade_values"),
        Index(
            "ix_prot_tripped",
            "status",
            "breaker_id",
            sqlite_where=text("status = 'TRIPPED'"),
        ),
    )

    breaker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_key: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, server_default=text("'*'")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    grade: Mapped[str] = mapped_column(Text, nullable=False)
    tripped_at: Mapped[str | None] = mapped_column(Text)
    cleared_at: Mapped[str | None] = mapped_column(Text)
    reason_json: Mapped[str | None] = mapped_column(Text)
    counters_json: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class ProtectionCounterRow(Base):
    __tablename__ = "protection_counters"

    breaker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_date: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_key: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, server_default=text("'*'")
    )
    counter_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class PortfolioDecompositionRow(Base):
    __tablename__ = "portfolio_decomposition"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(Text, primary_key=True)
    sub_alloc_krw: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    is_legacy: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class PortfolioDecompositionMetaRow(Base):
    __tablename__ = "portfolio_decomposition_meta"
    __table_args__ = (Index("ix_decomp_meta_asof", "as_of"),)

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of: Mapped[str] = mapped_column(Text, nullable=False)
    v_total_at_save: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    v_a_at_save_json: Mapped[str] = mapped_column(Text, nullable=False)
    targets_capped_json: Mapped[str] = mapped_column(Text, nullable=False)
    targets_version: Mapped[int | None] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class SatelliteStateRow(Base):
    __tablename__ = "satellite_state"

    sub_sleeve_id: Mapped[str] = mapped_column(Text, primary_key=True)
    lookback_months: Mapped[int] = mapped_column(Integer, nullable=False)
    current_holding_key: Mapped[str | None] = mapped_column(Text)
    stage_pct: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    last_eval_date: Mapped[str | None] = mapped_column(Text)
    peak_krw: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    dd_stage: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    dd_entered_at: Mapped[str | None] = mapped_column(Text)
    cooldown_until: Mapped[str | None] = mapped_column(Text)
    carryover_pct: Mapped[Decimal] = mapped_column(
        DecimalText(), nullable=False, server_default=text("'0'")
    )
    ytd_turnover_pct: Mapped[Decimal] = mapped_column(
        DecimalText(), nullable=False, server_default=text("'0'")
    )
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class UnmatchedFillRow(Base):
    __tablename__ = "unmatched_fills"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING','ABSORBED','DISCARDED')", name="state_values"),
        UniqueConstraint("broker_exec_id"),
        Index(
            "ix_unmatched_open",
            "account_id",
            "state",
            "filled_at_kst",
            sqlite_where=text("state = 'PENDING'"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_key: Mapped[str] = mapped_column(Text, nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    price: Mapped[Decimal] = mapped_column(DecimalText(), nullable=False)
    filled_at_kst: Mapped[datetime] = mapped_column(KSTDateTimeText(), nullable=False)
    broker_exec_id: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)


class NotificationSuppressionRow(Base):
    __tablename__ = "notification_suppression"

    subject_key: Mapped[str] = mapped_column(Text, primary_key=True)
    reason_key: Mapped[str] = mapped_column(Text, primary_key=True)
    last_sent_date: Mapped[str] = mapped_column(Text, nullable=False)
    last_sent_at: Mapped[str] = mapped_column(Text, nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


TABLE_NAMES: Final[frozenset[str]] = frozenset(Base.metadata.tables)

__all__ = [
    "NAMING_CONVENTION",
    "TABLE_NAMES",
    "ApprovalRequestRow",
    "Base",
    "BotStateRow",
    "BrokerTokenRow",
    "CanaryStateRow",
    "ChangeBudgetRow",
    "ContributionLedgerRow",
    "ExecutionStateRow",
    "ExperimentEventRow",
    "ExperimentRow",
    "FillRow",
    "HarvestLedgerRow",
    "MarketHolidayRow",
    "NavSnapshotRow",
    "NotificationSuppressionRow",
    "OrderRow",
    "PendingTaxEventRow",
    "PendingTransferRow",
    "PolicyVersionRow",
    "PortfolioDecompositionMetaRow",
    "PortfolioDecompositionRow",
    "PositionRow",
    "PresenceRow",
    "ProtectionCounterRow",
    "ProtectionStateRow",
    "RebalancePlanRow",
    "ReconcileExpectationRow",
    "ResearchExtractionRow",
    "RunLedgerRow",
    "SatelliteStateRow",
    "SleeveStateRow",
    "SurveillanceFlagRow",
    "TaxEventRow",
    "TaxbaseSnapshotRow",
    "UnmatchedFillRow",
]
