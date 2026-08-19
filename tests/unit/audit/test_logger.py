"""Durable append-only audit writer contracts."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from tests.support.masking import MASKING_CASES, MaskingCase

from omra.audit import (
    Actor,
    AuditLogger,
    AuditValidationError,
    AuditWriteError,
    Correlation,
    EventType,
    OrderIoPayload,
    PlanDecisionPayload,
    read_audit_line,
)
from omra.brokers.masking import Masker
from omra.core import SimClock, new_id

if TYPE_CHECKING:
    from pathlib import Path


def _clock() -> SimClock:
    return SimClock(datetime(2026, 8, 19, 3, 34, 56, tzinfo=UTC))


def _decision(reason: str | None = None) -> PlanDecisionPayload:
    return PlanDecisionPayload(plan_id="PLAN-1", reason=reason)


def test_live_writer_appends_utf8_one_line_events_with_kst_and_ulid(tmp_path: Path) -> None:
    root = tmp_path / "audit"
    with AuditLogger(root, clock=_clock()) as logger:
        event_id = logger.emit(
            EventType.PLAN_APPROVED,
            _decision("사용자 승인"),
            actor=Actor.USER,
        )

    path = root / "2026-08.jsonl"
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 1
    assert re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", event_id)
    event = read_audit_line(raw.decode("utf-8"))
    assert event.event_id == event_id
    assert event.ts_kst == "2026-08-19T12:34:56+09:00"
    assert isinstance(event.payload, PlanDecisionPayload)
    assert event.payload.reason == "사용자 승인"


def test_new_logger_process_appends_without_overwriting_existing_lines(tmp_path: Path) -> None:
    root = tmp_path / "audit"
    for reason in ("first", "second"):
        with AuditLogger(root, clock=_clock()) as logger:
            logger.emit(EventType.PLAN_APPROVED, _decision(reason), actor=Actor.USER)

    events = [
        read_audit_line(line)
        for line in (root / "2026-08.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(events) == 2
    reasons: list[str | None] = []
    for event in events:
        assert isinstance(event.payload, PlanDecisionPayload)
        reasons.append(event.payload.reason)
    assert reasons == ["first", "second"]


@pytest.mark.parametrize("case", MASKING_CASES, ids=lambda case: case.case_id)
def test_audit_serialization_uses_shared_masking_vectors(
    case: MaskingCase,
    tmp_path: Path,
) -> None:
    root = tmp_path / case.case_id
    payload = OrderIoPayload(
        broker="dummy",
        env="paper",
        request_raw=case.payload,
        response_raw=None,
        dry_run=True,
    )
    with AuditLogger(
        root,
        clock=_clock(),
        masker=Masker([case.registered_value]),
    ) as logger:
        logger.emit(EventType.ORDER_SUBMITTED, payload, actor=Actor.SCHEDULER)

    rendered = (root / "2026-08.jsonl").read_text(encoding="utf-8")
    assert case.forbidden not in rendered
    assert "***" in rendered


def test_backtest_writer_isolated_from_live_month_and_injects_run_correlation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "audit"
    run_id = new_id()
    with AuditLogger(root, clock=_clock(), backtest_run_id=run_id) as logger:
        logger.emit(EventType.PLAN_APPROVED, _decision(), actor=Actor.LABS)

    assert list(root.glob("*.jsonl")) == []
    path = root / "backtest" / f"{run_id}.jsonl"
    event = read_audit_line(path.read_text(encoding="utf-8"))
    assert event.actor is Actor.LABS
    assert event.correlation.run_id == run_id


def test_backtest_writer_rejects_non_labs_actor_and_mismatched_run_id(tmp_path: Path) -> None:
    run_id = new_id()
    logger = AuditLogger(tmp_path, clock=_clock(), backtest_run_id=run_id)

    with pytest.raises(AuditValidationError, match="actor='labs'"):
        logger.emit(EventType.PLAN_APPROVED, _decision(), actor=Actor.USER)
    with pytest.raises(AuditValidationError, match="must equal"):
        logger.emit(
            EventType.PLAN_APPROVED,
            _decision(),
            actor=Actor.LABS,
            correlation=Correlation(run_id=new_id()),
        )
    logger.close()


def test_month_rollover_loses_no_event_and_opens_distinct_files(tmp_path: Path) -> None:
    clock = SimClock(datetime(2026, 8, 31, 14, 59, 59, tzinfo=UTC))
    logger = AuditLogger(tmp_path, clock=clock)
    first = logger.emit(EventType.PLAN_APPROVED, _decision("august"), actor=Actor.USER)

    clock.advance(timedelta(seconds=2))
    logger.rollover_check()
    assert (tmp_path / "2026-09.jsonl").is_file()
    second = logger.emit(EventType.PLAN_APPROVED, _decision("september"), actor=Actor.USER)
    logger.close()

    august = (tmp_path / "2026-08.jsonl").read_text(encoding="utf-8").splitlines()
    september = (tmp_path / "2026-09.jsonl").read_text(encoding="utf-8").splitlines()
    assert [read_audit_line(line).event_id for line in august + september] == [first, second]


def test_writer_flushes_and_fsyncs_every_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def record_fsync(file_descriptor: int) -> None:
        calls.append(file_descriptor)

    monkeypatch.setattr("omra.audit.logger.os.fsync", record_fsync)
    with AuditLogger(tmp_path, clock=_clock()) as logger:
        logger.emit(EventType.PLAN_APPROVED, _decision("one"), actor=Actor.USER)
        logger.emit(EventType.PLAN_APPROVED, _decision("two"), actor=Actor.USER)

    assert len(calls) == 2
    assert all(file_descriptor >= 0 for file_descriptor in calls)


def test_fsync_failure_is_propagated_as_audit_write_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_fsync(_file_descriptor: int) -> None:
        raise OSError("dummy disk failure")

    monkeypatch.setattr("omra.audit.logger.os.fsync", fail_fsync)
    logger = AuditLogger(tmp_path, clock=_clock())

    with pytest.raises(AuditWriteError, match="durably appended"):
        logger.emit(EventType.PLAN_APPROVED, _decision(), actor=Actor.USER)
    logger.close()


def test_writer_rejects_event_payload_registry_mismatch(tmp_path: Path) -> None:
    logger = AuditLogger(tmp_path, clock=_clock())

    with pytest.raises(AuditValidationError, match="OrderIoPayload"):
        logger.emit(EventType.ORDER_SUBMITTED, _decision(), actor=Actor.SCHEDULER)
    logger.close()


@pytest.mark.parametrize("run_id", ["", "not-a-ulid", "01J0000000000000000000000I"])
def test_backtest_writer_rejects_non_ulid_run_id(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(AuditValidationError, match="ULID"):
        AuditLogger(tmp_path, clock=_clock(), backtest_run_id=run_id)
