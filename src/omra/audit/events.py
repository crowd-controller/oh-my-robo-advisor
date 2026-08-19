"""Version-one audit envelope and event-specific payload registry."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date  # noqa: TC003 - Pydantic resolves this annotation at runtime
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializeAsAny,
    ValidationInfo,
    field_validator,
    model_validator,
)

from omra.core import from_kst_text


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class Actor(StrEnum):
    SCHEDULER = "scheduler"
    USER = "user"
    GUARD = "guard"
    SURVEILLANCE = "surveillance"
    LABS = "labs"


class EventType(StrEnum):
    TARGETS_COMPUTED = "targets_computed"
    PLAN_CREATED = "plan_created"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    GUARD_VERDICT = "guard_verdict"
    SURVEILLANCE_TRANSITION = "surveillance_transition"
    PROTECTION_TRIPPED = "protection_tripped"
    STATE_TRANSITION = "state_transition"
    CONFIG_CHANGED = "config_changed"
    TOKEN_ISSUED = "token_issued"  # noqa: S105 - audit event name, not a credential
    LLM_CALL = "llm_call"
    RECONCILE_WHITELISTED = "reconcile_whitelisted"
    FX_SNAPSHOT_APPLIED = "fx_snapshot_applied"
    CANARY_STEP = "canary_step"
    BUDGET_CONSUMED = "budget_consumed"
    ROLLBACK_FIRED = "rollback_fired"
    RPC_COMMAND = "rpc_command"
    CASSETTE_SMOKE = "cassette_smoke"
    UNMATCHED_FILL = "unmatched_fill"


class BlockedBy(StrEnum):
    DEFER = "DEFER"
    SHRINK = "SHRINK"
    ABORT = "ABORT"
    SV2 = "SV2"
    SV3 = "SV3"
    SAFE_MODE_CAP = "SAFE_MODE_CAP"
    TAX_SOFT_STOP = "TAX_SOFT_STOP"
    TAX_ISA_LIMIT = "TAX_ISA_LIMIT"


class TrackingErrorComponent(StrEnum):
    COST = "1_cost"
    GUARD_SURVEILLANCE = "3_guard_surveillance"
    SAFE_MODE = "4_safe_mode"


_BLOCKED_BY_COMPONENT: Mapping[BlockedBy, TrackingErrorComponent] = MappingProxyType(
    {
        BlockedBy.DEFER: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SHRINK: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.ABORT: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SV2: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SV3: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SAFE_MODE_CAP: TrackingErrorComponent.SAFE_MODE,
        BlockedBy.TAX_SOFT_STOP: TrackingErrorComponent.COST,
        BlockedBy.TAX_ISA_LIMIT: TrackingErrorComponent.COST,
    }
)


def tracking_error_component(blocked_by: BlockedBy) -> TrackingErrorComponent:
    """Map every canonical block reason to exactly one tracking-error component."""
    return _BLOCKED_BY_COMPONENT[blocked_by]


class Correlation(_FrozenModel):
    plan_id: str | None = None
    order_id: str | None = None
    change_id: str | None = None
    run_id: str | None = None
    source_event_id: str | None = None


class AuditPayload(_FrozenModel):
    """Base type for event-specific payload models."""


class TargetsComputedPayload(AuditPayload):
    as_of: date
    sleeve: str
    weights: dict[str, str]
    method: str
    inputs_hash: str


class PlanCreatedPayload(AuditPayload):
    plan_id: str
    as_of_kst: str
    reason: str
    order_ids: tuple[str, ...]
    expected_turnover: str
    sanity_passed: bool

    @field_validator("as_of_kst")
    @classmethod
    def _validate_as_of_kst(cls, value: str) -> str:
        from_kst_text(value)
        return value


class PlanDecisionPayload(AuditPayload):
    plan_id: str
    reason: str | None = None


class OrderIoPayload(AuditPayload):
    broker: str
    env: str
    request_raw: dict[str, JsonValue]
    response_raw: dict[str, JsonValue] | None
    dry_run: bool


class OrderFilledPayload(AuditPayload):
    order_id: str
    fill_id: str
    qty: str
    price: str
    fee: str | None = None
    tax: str | None = None
    filled_at_kst: str
    settle_date: date
    broker_exec_id: str | None = None
    response_raw: dict[str, JsonValue] | None = None

    @field_validator("filled_at_kst")
    @classmethod
    def _validate_filled_at_kst(cls, value: str) -> str:
        from_kst_text(value)
        return value


class CounterfactualOrder(_FrozenModel):
    instrument_key: str
    side: Literal["buy", "sell"]
    qty: str
    ref_price: str
    notional_krw: int


class GuardVerdictPayload(AuditPayload):
    verdict: Literal["DEFER", "SHRINK", "ABORT"] | None
    blocked_by: BlockedBy
    scope: Literal["instrument", "venue"]
    sides: tuple[Literal["buy", "sell"], ...]
    guard: str
    reason: str
    limit_price_hint: str | None
    counterfactual: CounterfactualOrder


class ReconcileWhitelistedPayload(AuditPayload):
    expectation_id: str
    kind: str
    observed: dict[str, JsonValue]
    matched_rule: str


class SurveillanceTransitionPayload(AuditPayload):
    instrument_key: str
    risk_type: str
    source: str
    before_level: int | None
    after_level: int
    state: str
    raw_excerpt: str


class LlmCallPayload(AuditPayload):
    purpose: str
    model: str
    prompt_hash: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    batch: bool


class RpcCommandPayload(AuditPayload):
    channel: str
    command: str
    args_masked: dict[str, JsonValue]
    level: str
    confirm_method: str | None
    accepted: bool
    reject_reason: str | None
    result_summary: str | None


class CassetteSmokePayload(AuditPayload):
    group: str
    drift_grade: Literal["D0", "D1", "D2"]
    targets: tuple[str, ...]
    rerecorded: bool
    report_path: str


class UnmatchedFillPayload(AuditPayload):
    unmatched_fill_id: str
    account_id: str
    instrument_key: str
    side: Literal["buy", "sell"]
    qty: str
    price: str
    broker_exec_id: str | None
    disposition: Literal["PENDING", "ABSORBED", "DISCARDED"]
    resolution: str | None


class ProtectionTrippedPayload(AuditPayload):
    breaker_id: str
    grade: str
    action: str
    scope_key: str
    observed: JsonValue
    clear_hint: str | None
    cleared: bool = False


class StateTransitionPayload(AuditPayload):
    plane: str
    before: str | None
    after: str | None
    cause: str
    actor: Actor
    breaker_id: str | None = None
    rejected: bool = False


class ConfigKeyDiff(_FrozenModel):
    path: str
    before: JsonValue = Field(alias="from")
    after: JsonValue = Field(alias="to")


class ConfigChangedPayload(AuditPayload):
    trigger: Literal["startup", "reload", "ci"]
    effective_before: str | None
    effective_after: str
    files_changed: tuple[str, ...]
    key_diff: tuple[ConfigKeyDiff, ...]


class TokenIssuedPayload(AuditPayload):
    kind: str
    credential_id: str
    expires_at_kst: str

    @field_validator("expires_at_kst")
    @classmethod
    def _validate_expires_at_kst(cls, value: str) -> str:
        from_kst_text(value)
        return value


class FxSnapshotAppliedPayload(AuditPayload):
    purpose: Literal["planning", "order", "settlement", "monitor", "backtest"]
    pair: str
    rate: str
    source: str
    run_date: date


class CanaryStepPayload(AuditPayload):
    change_id: str
    before: str
    after: str
    step_index: int = Field(ge=0)
    kind: Literal["ADVANCE", "HOLD", "COMPLETE", "ROLLBACK"]
    target: str


class BudgetConsumedPayload(AuditPayload):
    year: int
    bucket: Literal["total", "targets", "params", "logic"]
    consumed: int = Field(ge=0)
    cap: int = Field(ge=0)
    action: Literal["initialize", "consume", "rollback"]
    change_id: str | None = None


class RollbackFiredPayload(AuditPayload):
    change_id: str
    trigger: str
    observed: str | None = None
    threshold: str | None = None
    window: str | None = None
    evidence: tuple[str, ...] = ()
    reason: str | None = None


PAYLOAD_MODELS: Mapping[EventType, type[AuditPayload]] = MappingProxyType(
    {
        EventType.TARGETS_COMPUTED: TargetsComputedPayload,
        EventType.PLAN_CREATED: PlanCreatedPayload,
        EventType.PLAN_APPROVED: PlanDecisionPayload,
        EventType.PLAN_REJECTED: PlanDecisionPayload,
        EventType.ORDER_SUBMITTED: OrderIoPayload,
        EventType.ORDER_FILLED: OrderFilledPayload,
        EventType.ORDER_CANCELLED: OrderIoPayload,
        EventType.ORDER_REJECTED: OrderIoPayload,
        EventType.GUARD_VERDICT: GuardVerdictPayload,
        EventType.SURVEILLANCE_TRANSITION: SurveillanceTransitionPayload,
        EventType.PROTECTION_TRIPPED: ProtectionTrippedPayload,
        EventType.STATE_TRANSITION: StateTransitionPayload,
        EventType.CONFIG_CHANGED: ConfigChangedPayload,
        EventType.TOKEN_ISSUED: TokenIssuedPayload,
        EventType.LLM_CALL: LlmCallPayload,
        EventType.RECONCILE_WHITELISTED: ReconcileWhitelistedPayload,
        EventType.FX_SNAPSHOT_APPLIED: FxSnapshotAppliedPayload,
        EventType.CANARY_STEP: CanaryStepPayload,
        EventType.BUDGET_CONSUMED: BudgetConsumedPayload,
        EventType.ROLLBACK_FIRED: RollbackFiredPayload,
        EventType.RPC_COMMAND: RpcCommandPayload,
        EventType.CASSETTE_SMOKE: CassetteSmokePayload,
        EventType.UNMATCHED_FILL: UnmatchedFillPayload,
    }
)


def payload_model_for(event_type: EventType | str) -> type[AuditPayload]:
    """Return the one payload model owned by an event type."""
    return PAYLOAD_MODELS[EventType(event_type)]


class AuditEvent(_FrozenModel):
    schema_version: Literal[1] = 1
    event_id: str = Field(pattern=r"^[0-9A-HJKMNP-TV-Z]{26}$")
    ts_kst: str
    event_type: EventType
    actor: Actor
    correlation: Correlation = Field(default_factory=Correlation)
    payload: SerializeAsAny[AuditPayload]

    @field_validator("ts_kst")
    @classmethod
    def _validate_ts_kst(cls, value: str) -> str:
        from_kst_text(value)
        return value

    @model_validator(mode="before")
    @classmethod
    def _validate_payload_model(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, Mapping):
            return value

        raw_event_type = value.get("event_type")
        if not isinstance(raw_event_type, (str, EventType)):
            return value
        try:
            event_type = EventType(raw_event_type)
        except ValueError:
            return value

        expected = payload_model_for(event_type)
        raw_payload = value.get("payload")
        if isinstance(raw_payload, expected):
            payload = raw_payload
        elif isinstance(raw_payload, AuditPayload):
            raise ValueError(f"{event_type.value} requires payload model {expected.__name__}")
        else:
            allow_unknown = bool(info.context and info.context.get("allow_unknown"))
            payload = expected.model_validate(
                raw_payload,
                extra="ignore" if allow_unknown else "forbid",
                context=info.context,
            )

        normalized = dict(value)
        normalized["payload"] = payload
        return normalized

    @model_validator(mode="after")
    def _validate_state_transition_actor(self) -> AuditEvent:
        if self.event_type is EventType.STATE_TRANSITION:
            if not isinstance(self.payload, StateTransitionPayload):
                raise ValueError("state_transition requires StateTransitionPayload")
            if self.payload.actor is not self.actor:
                raise ValueError("state_transition payload actor must equal envelope actor")
        return self
