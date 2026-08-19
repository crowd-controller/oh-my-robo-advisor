"""Durable append-only JSONL audit writer."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from pydantic import ValidationError

from omra.audit.errors import AuditValidationError, AuditWriteError
from omra.audit.events import (
    Actor,
    AuditEvent,
    AuditPayload,
    Correlation,
    EventType,
    payload_model_for,
)
from omra.brokers.masking import Masker
from omra.core import Clock, new_id, to_kst_text

if TYPE_CHECKING:
    from types import TracebackType
    from typing import TextIO

_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


class AuditLogger:
    """Append validated events and force each one to durable storage."""

    def __init__(
        self,
        root: str | Path,
        *,
        clock: Clock,
        masker: Masker | None = None,
        backtest_run_id: str | None = None,
    ) -> None:
        if backtest_run_id is not None and _ULID_PATTERN.fullmatch(backtest_run_id) is None:
            raise AuditValidationError("backtest run_id must be a 26-character ULID")
        self._root = Path(root)
        self._clock = clock
        self._masker = masker or Masker()
        self._backtest_run_id = backtest_run_id
        self._lock = Lock()
        self._handle: TextIO | None = None
        self._open_path: Path | None = None

    def __enter__(self) -> AuditLogger:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _normalize_correlation(
        self,
        *,
        actor: Actor,
        correlation: Correlation | None,
    ) -> Correlation:
        normalized = correlation or Correlation()
        if self._backtest_run_id is None:
            return normalized
        if actor is not Actor.LABS:
            raise AuditValidationError("backtest audit events require actor='labs'")
        if normalized.run_id not in {None, self._backtest_run_id}:
            raise AuditValidationError("backtest correlation.run_id must equal the logger run_id")
        if normalized.run_id is None:
            normalized = normalized.model_copy(update={"run_id": self._backtest_run_id})
        return normalized

    def _path_for(self, event: AuditEvent) -> Path:
        if self._backtest_run_id is not None:
            return self._root / "backtest" / f"{self._backtest_run_id}.jsonl"
        return self._root / f"{event.ts_kst[:7]}.jsonl"

    def _close_current(self) -> None:
        if self._handle is not None:
            self._handle.close()
        self._handle = None
        self._open_path = None

    def _ensure_handle(self, path: Path) -> TextIO:
        if self._handle is not None and self._open_path == path:
            return self._handle
        self._close_current()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("a", encoding="utf-8", newline="\n")
        self._open_path = path
        return self._handle

    def emit(
        self,
        event_type: EventType | str,
        payload: AuditPayload,
        *,
        actor: Actor | str,
        correlation: Correlation | None = None,
    ) -> str:
        """Validate, mask, append, flush, and fsync one event; return its ULID."""
        try:
            normalized_type = EventType(event_type)
            normalized_actor = Actor(actor)
        except (TypeError, ValueError) as error:
            raise AuditValidationError("unknown audit event type or actor") from error

        expected_payload = payload_model_for(normalized_type)
        if payload.__class__ is not expected_payload:
            raise AuditValidationError(
                f"{normalized_type.value} requires payload model {expected_payload.__name__}"
            )
        normalized_correlation = self._normalize_correlation(
            actor=normalized_actor,
            correlation=correlation,
        )

        try:
            event = AuditEvent(
                event_id=new_id(),
                ts_kst=to_kst_text(self._clock.now_kst()),
                event_type=normalized_type,
                actor=normalized_actor,
                correlation=normalized_correlation,
                payload=payload,
            )
        except ValidationError as error:
            raise AuditValidationError(
                "audit event failed schema validation",
                context={"event_type": normalized_type.value},
            ) from error

        target = self._path_for(event)
        try:
            serialized = event.model_dump(
                mode="json",
                by_alias=True,
                serialize_as_any=True,
            )
            masked = self._masker.mask(serialized, direction="res")
            line = (
                json.dumps(
                    masked,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )
            with self._lock:
                handle = self._ensure_handle(target)
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        except (OSError, TypeError, UnicodeError, ValueError) as error:
            raise AuditWriteError(
                "audit event could not be durably appended",
                context={
                    "event_id": event.event_id,
                    "path": str(target),
                },
            ) from error
        return event.event_id

    def rollover_check(self) -> None:
        """Replace a stale live-month append handle with the current month's handle."""
        if self._backtest_run_id is not None:
            return
        current_path = self._root / f"{to_kst_text(self._clock.now_kst())[:7]}.jsonl"
        with self._lock:
            if self._handle is not None and self._open_path != current_path:
                try:
                    self._ensure_handle(current_path)
                except OSError as error:
                    raise AuditWriteError(
                        "audit month rollover failed",
                        context={"path": str(current_path)},
                    ) from error

    def close(self) -> None:
        """Close the current append handle and propagate close failures."""
        with self._lock:
            try:
                self._close_current()
            except OSError as error:
                raise AuditWriteError(
                    "audit file could not be closed",
                    context={"path": str(self._open_path)},
                ) from error
