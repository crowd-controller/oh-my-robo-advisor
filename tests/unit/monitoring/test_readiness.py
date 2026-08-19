"""Unit contracts for the local-only M0 readiness probe."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from omra.core import SimClock
from omra.monitoring.readiness import (
    CheckStatus,
    ReadinessCheck,
    ReadinessProbe,
    ReadinessReport,
    ReadinessStatus,
)

_ROOT = Path(__file__).resolve().parents[3]
_REVISION = "0001_sqlite_schema"


def _clock() -> SimClock:
    return SimClock(datetime(2026, 8, 19, tzinfo=UTC))


def _migrate(tmp_path: Path) -> Path:
    runtime = tmp_path / "var"
    db_dir = runtime / "db"
    db_dir.mkdir(parents=True)
    (runtime / "data").mkdir()
    db_path = db_dir / "omra.sqlite"
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(_ROOT / "src" / "omra" / "persistence" / "migrations"),
    )
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(config, "head")
    return db_path


def test_report_derives_not_ready_from_the_worst_check() -> None:
    report = ReadinessReport.from_checks(
        checks=(
            ReadinessCheck(id="config", status=CheckStatus.OK),
            ReadinessCheck(
                id="database",
                status=CheckStatus.FAIL,
                code="database_unavailable",
            ),
            ReadinessCheck(id="schema", status=CheckStatus.OK),
            ReadinessCheck(id="volumes", status=CheckStatus.OK),
        ),
        generated_at=_clock().now_utc(),
        version="0.1.0",
    )

    assert report.status is ReadinessStatus.NOT_READY
    assert report.model_dump(mode="json") == {
        "status": "not_ready",
        "checks": [
            {"id": "config", "status": "pass", "code": None},
            {
                "id": "database",
                "status": "fail",
                "code": "database_unavailable",
            },
            {"id": "schema", "status": "pass", "code": None},
            {"id": "volumes", "status": "pass", "code": None},
        ],
        "generated_at": "2026-08-19T00:00:00Z",
        "version": "0.1.0",
    }


def test_probe_reports_ready_for_valid_config_schema_and_volumes(tmp_path: Path) -> None:
    db_path = _migrate(tmp_path)
    data_path = tmp_path / "var" / "data"
    logs_path = tmp_path / "var" / "logs"
    policy_path = tmp_path / "var" / "policy"
    logs_path.mkdir()
    policy_path.mkdir()
    probe = ReadinessProbe(
        config_dir=_ROOT / "config",
        db_path=db_path,
        writable_dirs=(db_path.parent, data_path, logs_path, policy_path),
        expected_revision=_REVISION,
        clock=_clock(),
        version="0.1.0",
    )

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        report = probe.collect()

    assert report.status is ReadinessStatus.READY
    assert tuple(check.id for check in report.checks) == (
        "config",
        "database",
        "schema",
        "volumes",
    )
    assert all(check.status is CheckStatus.OK for check in report.checks)
    assert not tuple(tmp_path.rglob(".omra-ready-*"))


def test_probe_bounds_config_and_schema_failures(tmp_path: Path) -> None:
    db_path = _migrate(tmp_path)
    config_dir = tmp_path / "missing-config"
    with db_path.open("r+b") as database:
        database.seek(0)
        database.write(b"not sqlite")
        database.truncate()
    probe = ReadinessProbe(
        config_dir=config_dir,
        db_path=db_path,
        writable_dirs=(db_path.parent,),
        expected_revision=_REVISION,
        clock=_clock(),
        version="0.1.0",
    )

    report = probe.collect()

    assert report.status is ReadinessStatus.NOT_READY
    assert tuple((check.id, check.code) for check in report.checks) == (
        ("config", "config_invalid"),
        ("database", "database_unavailable"),
        ("schema", "schema_unavailable"),
        ("volumes", None),
    )
    assert "missing-config" not in report.model_dump_json()


def test_probe_rejects_a_non_head_revision_and_unwritable_target(tmp_path: Path) -> None:
    db_path = _migrate(tmp_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE alembic_version SET version_num='outdated'")
        connection.commit()
    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("occupied", encoding="utf-8")
    probe = ReadinessProbe(
        config_dir=_ROOT / "config",
        db_path=db_path,
        writable_dirs=(not_a_directory,),
        expected_revision=_REVISION,
        clock=_clock(),
        version="0.1.0",
    )

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        report = probe.collect()

    assert tuple((check.id, check.code) for check in report.checks) == (
        ("config", None),
        ("database", None),
        ("schema", "schema_revision_mismatch"),
        ("volumes", "volume_unwritable"),
    )


def test_probe_bounds_probe_file_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = _migrate(tmp_path)
    probe = ReadinessProbe(
        config_dir=_ROOT / "config",
        db_path=db_path,
        writable_dirs=(db_path.parent,),
        expected_revision=_REVISION,
        clock=_clock(),
        version="0.1.0",
    )
    original_unlink = Path.unlink

    def fail_probe_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        if path.name.startswith(".omra-ready-"):
            raise OSError("operator path detail")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_probe_cleanup)

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        report = probe.collect()

    assert report.status is ReadinessStatus.NOT_READY
    assert report.checks[-1].code == "volume_unwritable"


def test_probe_rejects_an_expected_head_plus_an_extra_revision(tmp_path: Path) -> None:
    db_path = _migrate(tmp_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO alembic_version(version_num) VALUES ('unexpected_revision')"
        )
        connection.commit()
    probe = ReadinessProbe(
        config_dir=_ROOT / "config",
        db_path=db_path,
        writable_dirs=(db_path.parent,),
        expected_revision=_REVISION,
        clock=_clock(),
        version="0.1.0",
    )

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        report = probe.collect()

    assert report.status is ReadinessStatus.NOT_READY
    assert report.checks[2].code == "schema_revision_mismatch"


def _wire_checks() -> list[dict[str, object]]:
    return [
        {"id": "config", "status": "pass", "code": None},
        {"id": "database", "status": "pass", "code": None},
        {"id": "schema", "status": "pass", "code": None},
        {"id": "volumes", "status": "pass", "code": None},
    ]


def _wire_payload(
    checks: list[dict[str, object]],
    *,
    status: str = "ready",
) -> dict[str, object]:
    return {
        "status": status,
        "checks": checks,
        "generated_at": "2026-08-19T00:00:00Z",
        "version": "0.1.0",
    }


def test_wire_report_rejects_empty_missing_duplicate_and_inconsistent_checks() -> None:
    inconsistent = _wire_checks()
    inconsistent[2] = {
        "id": "schema",
        "status": "fail",
        "code": "schema_revision_mismatch",
    }
    invalid_payloads = (
        _wire_payload([]),
        _wire_payload(_wire_checks()[:-1]),
        _wire_payload([*_wire_checks(), _wire_checks()[0]]),
        _wire_payload(inconsistent),
    )

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            ReadinessReport.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "config", "status": "pass", "code": "config_invalid"},
        {"id": "database", "status": "fail", "code": None},
        {"id": "schema", "status": "fail", "code": "database_unavailable"},
    ],
)
def test_wire_check_rejects_inconsistent_or_wrong_failure_codes(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ReadinessCheck.model_validate(payload)
