"""Credential-free, local-only readiness checks for the M0 container shell."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime  # noqa: TC003 - Pydantic resolves this runtime annotation
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from omra.config import ConfigError, load_and_validate_config

if TYPE_CHECKING:
    from omra.core import Clock


class CheckStatus(StrEnum):
    """Result of one bounded readiness check."""

    OK = "pass"
    FAIL = "fail"


class ReadinessStatus(StrEnum):
    """Whether the M0 process can serve its local container contract."""

    READY = "ready"
    NOT_READY = "not_ready"


CheckId = Literal["config", "database", "schema", "volumes"]
FailureCode = Literal[
    "config_invalid",
    "database_unavailable",
    "schema_unavailable",
    "schema_revision_mismatch",
    "volume_unwritable",
]
_CHECK_IDS: Final[tuple[CheckId, ...]] = ("config", "database", "schema", "volumes")
_FAILURE_CODES: Final[dict[CheckId, frozenset[FailureCode]]] = {
    "config": frozenset({"config_invalid"}),
    "database": frozenset({"database_unavailable"}),
    "schema": frozenset({"schema_unavailable", "schema_revision_mismatch"}),
    "volumes": frozenset({"volume_unwritable"}),
}


class ReadinessCheck(BaseModel):
    """One check with a stable diagnostic code and no sensitive detail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: CheckId
    status: CheckStatus
    code: FailureCode | None = None

    @model_validator(mode="after")
    def _validate_status_code(self) -> Self:
        if self.status is CheckStatus.OK:
            if self.code is not None:
                raise ValueError("passing readiness checks cannot include a failure code")
            return self
        if self.code not in _FAILURE_CODES[self.id]:
            raise ValueError("failed readiness check has an invalid failure code")
        return self


class ReadinessReport(BaseModel):
    """Versioned readiness response consumed by Docker and operators."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ReadinessStatus
    checks: tuple[ReadinessCheck, ...]
    generated_at: datetime
    version: str

    @model_validator(mode="after")
    def _validate_aggregate(self) -> Self:
        check_ids = tuple(check.id for check in self.checks)
        if check_ids != _CHECK_IDS:
            raise ValueError("readiness checks must match the canonical ordered set")
        expected_status = (
            ReadinessStatus.READY
            if all(check.status is CheckStatus.OK for check in self.checks)
            else ReadinessStatus.NOT_READY
        )
        if self.status is not expected_status:
            raise ValueError("readiness aggregate status does not match its checks")
        return self

    @classmethod
    def from_checks(
        cls,
        *,
        checks: tuple[ReadinessCheck, ...],
        generated_at: datetime,
        version: str,
    ) -> ReadinessReport:
        """Derive the aggregate status rather than accepting it from callers."""
        status = (
            ReadinessStatus.READY
            if all(check.status is CheckStatus.OK for check in checks)
            else ReadinessStatus.NOT_READY
        )
        return cls(
            status=status,
            checks=checks,
            generated_at=generated_at,
            version=version,
        )


class ReadinessProbe:
    """Collect deterministic local filesystem, SQLite, and config observations."""

    def __init__(
        self,
        *,
        config_dir: Path,
        db_path: Path,
        writable_dirs: tuple[Path, ...],
        expected_revision: str,
        clock: Clock,
        version: str,
    ) -> None:
        self._config_dir = config_dir
        self._db_path = db_path
        self._writable_dirs = writable_dirs
        self._expected_revision = expected_revision
        self._clock = clock
        self._version = version

    @staticmethod
    def _pass(check_id: CheckId) -> ReadinessCheck:
        return ReadinessCheck(id=check_id, status=CheckStatus.OK)

    @staticmethod
    def _fail(check_id: CheckId, code: FailureCode) -> ReadinessCheck:
        return ReadinessCheck(id=check_id, status=CheckStatus.FAIL, code=code)

    def _check_config(self) -> ReadinessCheck:
        try:
            load_and_validate_config(self._config_dir, clock=self._clock)
        except (ConfigError, OSError):
            return self._fail("config", "config_invalid")
        return self._pass("config")

    def _read_only_connection(self) -> sqlite3.Connection:
        uri = f"{self._db_path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def _check_database(self) -> ReadinessCheck:
        try:
            with self._read_only_connection() as connection:
                connection.execute("PRAGMA schema_version").fetchone()
        except (OSError, sqlite3.Error):
            return self._fail("database", "database_unavailable")
        return self._pass("database")

    def _check_schema(self) -> ReadinessCheck:
        try:
            with self._read_only_connection() as connection:
                rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        except (OSError, sqlite3.Error):
            return self._fail("schema", "schema_unavailable")
        revisions = tuple(str(row[0]) for row in rows)
        if revisions != (self._expected_revision,):
            return self._fail("schema", "schema_revision_mismatch")
        return self._pass("schema")

    def _check_volumes(self) -> ReadinessCheck:
        for directory in self._writable_dirs:
            probe_path: Path | None = None
            check_failed = False
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=".omra-ready-",
                    dir=directory,
                    delete=False,
                ) as probe:
                    probe_path = Path(probe.name)
                    probe.write(b"ready")
                    probe.flush()
                    os.fsync(probe.fileno())
            except OSError:
                check_failed = True
            finally:
                if probe_path is not None:
                    try:
                        probe_path.unlink(missing_ok=True)
                    except OSError:
                        check_failed = True
            if check_failed:
                return self._fail("volumes", "volume_unwritable")
        return self._pass("volumes")

    def collect(self) -> ReadinessReport:
        """Return fresh local observations without any external network access."""
        checks = (
            self._check_config(),
            self._check_database(),
            self._check_schema(),
            self._check_volumes(),
        )
        return ReadinessReport.from_checks(
            checks=checks,
            generated_at=self._clock.now_utc(),
            version=self._version,
        )


__all__ = [
    "CheckStatus",
    "ReadinessCheck",
    "ReadinessProbe",
    "ReadinessReport",
    "ReadinessStatus",
]
