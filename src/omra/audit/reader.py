"""Forward-compatible reader for schema-version-one audit JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator

from omra.audit.errors import AuditReadError
from omra.audit.events import AuditEvent


def read_audit_line(line: str) -> AuditEvent:
    """Decode one v1 audit line while ignoring additive unknown fields."""
    try:
        decoded = json.loads(line)
    except json.JSONDecodeError as error:
        raise AuditReadError("audit line is not valid JSON") from error

    if not isinstance(decoded, dict):
        raise AuditReadError("audit line root must be a JSON object")
    if decoded.get("schema_version") != 1:
        raise AuditReadError(
            "unsupported audit schema version",
            context={"schema_version": str(decoded.get("schema_version"))},
        )

    try:
        return AuditEvent.model_validate(
            decoded,
            extra="ignore",
            context={"allow_unknown": True},
        )
    except ValidationError as error:
        raise AuditReadError("audit line does not match schema version 1") from error


def iter_audit_file(path: str | Path) -> Iterator[AuditEvent]:
    """Yield validated events from an audit JSONL file in order."""
    source = Path(path)
    try:
        with source.open(encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    yield read_audit_line(line)
                except AuditReadError as error:
                    raise AuditReadError(
                        str(error),
                        context={
                            **error.context,
                            "path": str(source),
                            "line_number": str(line_number),
                        },
                    ) from error
    except OSError as error:
        raise AuditReadError(
            "audit file could not be read",
            context={"path": str(source)},
        ) from error
