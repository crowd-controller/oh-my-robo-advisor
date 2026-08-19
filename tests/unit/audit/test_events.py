"""Canonical audit envelope and payload-registry contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.audit import (
    PAYLOAD_MODELS,
    Actor,
    AuditEvent,
    AuditPayload,
    BlockedBy,
    Correlation,
    EventType,
    GuardVerdictPayload,
    OrderIoPayload,
    PlanDecisionPayload,
    StateTransitionPayload,
    TrackingErrorComponent,
    tracking_error_component,
)
from omra.core import new_id

_TIMESTAMP = "2026-08-19T12:34:56+09:00"
_GOLDEN = Path(__file__).resolve().parents[3] / "tests" / "golden" / "audit"


def test_event_type_vocabulary_and_registry_are_total() -> None:
    assert [event_type.value for event_type in EventType] == [
        "targets_computed",
        "plan_created",
        "plan_approved",
        "plan_rejected",
        "order_submitted",
        "order_filled",
        "order_cancelled",
        "order_rejected",
        "guard_verdict",
        "surveillance_transition",
        "protection_tripped",
        "state_transition",
        "config_changed",
        "token_issued",
        "llm_call",
        "reconcile_whitelisted",
        "fx_snapshot_applied",
        "canary_step",
        "budget_consumed",
        "rollback_fired",
        "rpc_command",
        "cassette_smoke",
        "unmatched_fill",
    ]
    assert set(PAYLOAD_MODELS) == set(EventType)
    assert all(issubclass(model, AuditPayload) for model in PAYLOAD_MODELS.values())


def test_envelope_parses_payload_with_the_registered_model() -> None:
    event = AuditEvent.model_validate(
        {
            "event_id": new_id(),
            "ts_kst": _TIMESTAMP,
            "event_type": "plan_approved",
            "actor": "user",
            "correlation": {},
            "payload": {"plan_id": "PLAN-1", "reason": None},
        }
    )

    assert isinstance(event.payload, PlanDecisionPayload)


def test_envelope_rejects_a_payload_model_owned_by_another_event_type() -> None:
    with pytest.raises(ValidationError, match="requires payload model PlanDecisionPayload"):
        AuditEvent(
            event_id=new_id(),
            ts_kst=_TIMESTAMP,
            event_type=EventType.PLAN_APPROVED,
            actor=Actor.USER,
            payload=OrderIoPayload(
                broker="dummy",
                env="paper",
                request_raw={},
                response_raw=None,
                dry_run=True,
            ),
        )


@pytest.mark.parametrize("missing", ["blocked_by", "counterfactual"])
def test_guard_verdict_rejects_missing_te_input(missing: str) -> None:
    payload = {
        "verdict": "DEFER",
        "blocked_by": "DEFER",
        "scope": "instrument",
        "sides": ["buy"],
        "guard": "spread",
        "reason": "dummy",
        "limit_price_hint": None,
        "counterfactual": {
            "instrument_key": "NASD:DUMMY",
            "side": "buy",
            "qty": "1",
            "ref_price": "10.00",
            "notional_krw": 10000,
        },
    }
    del payload[missing]

    with pytest.raises(ValidationError):
        GuardVerdictPayload.model_validate(payload)


def test_every_block_reason_maps_to_exactly_one_tracking_error_component() -> None:
    expected = {
        BlockedBy.DEFER: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SHRINK: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.ABORT: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SV2: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SV3: TrackingErrorComponent.GUARD_SURVEILLANCE,
        BlockedBy.SAFE_MODE_CAP: TrackingErrorComponent.SAFE_MODE,
        BlockedBy.TAX_SOFT_STOP: TrackingErrorComponent.COST,
        BlockedBy.TAX_ISA_LIMIT: TrackingErrorComponent.COST,
    }

    assert {reason: tracking_error_component(reason) for reason in BlockedBy} == expected


def test_state_transition_payload_actor_must_match_envelope_actor() -> None:
    with pytest.raises(ValidationError, match="payload actor must equal envelope actor"):
        AuditEvent(
            event_id=new_id(),
            ts_kst=_TIMESTAMP,
            event_type=EventType.STATE_TRANSITION,
            actor=Actor.SCHEDULER,
            correlation=Correlation(),
            payload=StateTransitionPayload(
                plane="execution",
                before="READY",
                after="PAUSED",
                cause="dummy",
                actor=Actor.USER,
            ),
        )


def test_v1_envelope_serialization_matches_golden_contract() -> None:
    event = AuditEvent(
        event_id="01J00000000000000000000000",
        ts_kst=_TIMESTAMP,
        event_type=EventType.PLAN_APPROVED,
        actor=Actor.USER,
        correlation=Correlation(),
        payload=PlanDecisionPayload(plan_id="PLAN-1", reason=None),
    )

    expected = json.loads((_GOLDEN / "v1_plan_approved.json").read_text(encoding="utf-8"))
    assert event.model_dump(mode="json", by_alias=True, serialize_as_any=True) == expected
