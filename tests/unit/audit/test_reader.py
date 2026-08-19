"""Schema-v1 audit reader compatibility and rejection contracts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from omra.audit import AuditReadError, PlanDecisionPayload, iter_audit_file, read_audit_line
from omra.audit.events import Actor, AuditEvent, Correlation, EventType
from omra.core import new_id

if TYPE_CHECKING:
    from pathlib import Path

_TIMESTAMP = "2026-08-19T12:34:56+09:00"


def _document() -> dict[str, object]:
    event = AuditEvent(
        event_id=new_id(),
        ts_kst=_TIMESTAMP,
        event_type=EventType.PLAN_APPROVED,
        actor=Actor.USER,
        correlation=Correlation(),
        payload=PlanDecisionPayload(plan_id="PLAN-1", reason=None),
    )
    return event.model_dump(mode="json", by_alias=True, serialize_as_any=True)


def test_v1_reader_ignores_additive_unknown_fields_at_every_model_level() -> None:
    document = _document()
    document["future_envelope"] = {"new": True}
    correlation = document["correlation"]
    payload = document["payload"]
    assert isinstance(correlation, dict)
    assert isinstance(payload, dict)
    correlation["future_correlation"] = "ignored"
    payload["future_payload"] = 7

    event = read_audit_line(json.dumps(document))

    assert event.event_type is EventType.PLAN_APPROVED
    assert isinstance(event.payload, PlanDecisionPayload)
    assert event.payload.plan_id == "PLAN-1"


@pytest.mark.parametrize(
    "line",
    [
        "{",
        "[]",
        json.dumps({**_document(), "schema_version": 2}),
        json.dumps({**_document(), "event_type": "future_event"}),
    ],
)
def test_reader_rejects_malformed_or_unsupported_lines(line: str) -> None:
    with pytest.raises(AuditReadError):
        read_audit_line(line)


def test_file_reader_preserves_failing_line_context(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(json.dumps(_document()) + "\n{\n", encoding="utf-8")

    with pytest.raises(AuditReadError) as raised:
        list(iter_audit_file(path))

    assert raised.value.context == {
        "path": str(path),
        "line_number": "2",
    }
