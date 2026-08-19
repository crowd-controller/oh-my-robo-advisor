"""Representative schema validation for every registered audit event payload."""

from __future__ import annotations

import pytest

from omra.audit import PAYLOAD_MODELS, Actor, AuditEvent, EventType
from omra.core import new_id

_TIMESTAMP = "2026-08-19T12:34:56+09:00"
_ORDER_IO: dict[str, object] = {
    "broker": "dummy",
    "env": "paper",
    "request_raw": {"symbol": "DUMMY"},
    "response_raw": {"accepted": True},
    "dry_run": True,
}
_PLAN_DECISION: dict[str, object] = {"plan_id": "PLAN-1", "reason": "dummy"}

_SAMPLES: dict[EventType, dict[str, object]] = {
    EventType.TARGETS_COMPUTED: {
        "as_of": "2026-08-19",
        "sleeve": "core",
        "weights": {"NASD:DUMMY": "1"},
        "method": "policy",
        "inputs_hash": "sha256:dummy",
    },
    EventType.PLAN_CREATED: {
        "plan_id": "PLAN-1",
        "as_of_kst": _TIMESTAMP,
        "reason": "scheduled",
        "order_ids": ["ORDER-1"],
        "expected_turnover": "0.01",
        "sanity_passed": True,
    },
    EventType.PLAN_APPROVED: _PLAN_DECISION,
    EventType.PLAN_REJECTED: _PLAN_DECISION,
    EventType.ORDER_SUBMITTED: _ORDER_IO,
    EventType.ORDER_FILLED: {
        "order_id": "ORDER-1",
        "fill_id": "FILL-1",
        "qty": "1",
        "price": "10.00",
        "fee": "0.01",
        "tax": None,
        "filled_at_kst": _TIMESTAMP,
        "settle_date": "2026-08-21",
        "broker_exec_id": "EXEC-1",
        "response_raw": {"accepted": True},
    },
    EventType.ORDER_CANCELLED: _ORDER_IO,
    EventType.ORDER_REJECTED: _ORDER_IO,
    EventType.GUARD_VERDICT: {
        "verdict": "DEFER",
        "blocked_by": "DEFER",
        "scope": "instrument",
        "sides": ["buy"],
        "guard": "spread",
        "reason": "dummy",
        "limit_price_hint": "10.00",
        "counterfactual": {
            "instrument_key": "NASD:DUMMY",
            "side": "buy",
            "qty": "1",
            "ref_price": "10.00",
            "notional_krw": 10000,
        },
    },
    EventType.SURVEILLANCE_TRANSITION: {
        "instrument_key": "NASD:DUMMY",
        "risk_type": "halt",
        "source": "dummy",
        "before_level": 1,
        "after_level": 2,
        "state": "ACTIVE",
        "raw_excerpt": "dummy evidence",
    },
    EventType.PROTECTION_TRIPPED: {
        "breaker_id": "P1",
        "grade": "B",
        "action": "SAFE_MODE",
        "scope_key": "global",
        "observed": {"value": 1},
        "clear_hint": "dummy",
        "cleared": False,
    },
    EventType.STATE_TRANSITION: {
        "plane": "bot",
        "before": "READY",
        "after": "PAUSED",
        "cause": "dummy",
        "actor": "user",
        "breaker_id": None,
        "rejected": False,
    },
    EventType.CONFIG_CHANGED: {
        "trigger": "reload",
        "effective_before": "sha256:before",
        "effective_after": "sha256:after",
        "files_changed": ["config/config.yaml"],
        "key_diff": [{"path": "safe_mode.enabled", "from": False, "to": True}],
    },
    EventType.TOKEN_ISSUED: {
        "kind": "kis_access",
        "credential_id": "CREDENTIAL-1",
        "expires_at_kst": _TIMESTAMP,
    },
    EventType.LLM_CALL: {
        "purpose": "monthly_report",
        "model": "dummy-model",
        "prompt_hash": "sha256:dummy",
        "input_tokens": 10,
        "output_tokens": 5,
        "batch": False,
    },
    EventType.RECONCILE_WHITELISTED: {
        "expectation_id": "EXPECTATION-1",
        "kind": "settlement",
        "observed": {"amount": "1"},
        "matched_rule": "1",
    },
    EventType.FX_SNAPSHOT_APPLIED: {
        "purpose": "planning",
        "pair": "USDKRW",
        "rate": "1300.00",
        "source": "dummy",
        "run_date": "2026-08-19",
    },
    EventType.CANARY_STEP: {
        "change_id": "CHANGE-1",
        "before": "0.25",
        "after": "0.50",
        "step_index": 2,
        "kind": "ADVANCE",
        "target": "policy",
    },
    EventType.BUDGET_CONSUMED: {
        "year": 2026,
        "bucket": "params",
        "consumed": 1,
        "cap": 4,
        "action": "consume",
        "change_id": "CHANGE-1",
    },
    EventType.ROLLBACK_FIRED: {
        "change_id": "CHANGE-1",
        "trigger": "R1",
        "observed": "0.4",
        "threshold": "0.3",
        "window": "rolling_6m",
        "evidence": ["EVENT-1"],
        "reason": "dummy",
    },
    EventType.RPC_COMMAND: {
        "channel": "telegram",
        "command": "pause",
        "args_masked": {},
        "level": "T1",
        "confirm_method": None,
        "accepted": True,
        "reject_reason": None,
        "result_summary": "paused",
    },
    EventType.CASSETTE_SMOKE: {
        "group": "kis.balance",
        "drift_grade": "D0",
        "targets": ["balance"],
        "rerecorded": False,
        "report_path": "var/reports/dummy.json",
    },
    EventType.UNMATCHED_FILL: {
        "unmatched_fill_id": "UNMATCHED-1",
        "account_id": "ACCOUNT-1",
        "instrument_key": "NASD:DUMMY",
        "side": "buy",
        "qty": "1",
        "price": "10.00",
        "broker_exec_id": None,
        "disposition": "PENDING",
        "resolution": None,
    },
}


@pytest.mark.parametrize("event_type", list(EventType), ids=lambda item: item.value)
def test_each_registered_event_parses_exactly_its_owned_payload(event_type: EventType) -> None:
    event = AuditEvent.model_validate(
        {
            "event_id": new_id(),
            "ts_kst": _TIMESTAMP,
            "event_type": event_type,
            "actor": Actor.USER,
            "correlation": {},
            "payload": _SAMPLES[event_type],
        }
    )

    assert event.payload.__class__ is PAYLOAD_MODELS[event_type]
