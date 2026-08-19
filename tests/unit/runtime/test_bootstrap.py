"""Fail-closed startup contracts for the M0 runtime shell."""

import shutil
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omra.core import SimClock
from omra.monitoring.readiness import ReadinessStatus
from omra.persistence.session import close_persistence
from omra.runtime.bootstrap import BootstrapError, RuntimePaths, bootstrap

_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _reset_persistence() -> Iterator[None]:
    close_persistence()
    yield
    close_persistence()


def _clock() -> SimClock:
    return SimClock(datetime(2026, 8, 19, tzinfo=UTC))


def _paths(tmp_path: Path) -> RuntimePaths:
    config_dir = tmp_path / "config"
    shutil.copytree(_ROOT / "config", config_dir)
    runtime = tmp_path / "var"
    return RuntimePaths(
        config_dir=config_dir,
        db_path=runtime / "db" / "omra.sqlite",
        data_dir=runtime / "data",
        logs_dir=runtime / "logs",
        policy_dir=runtime / "policy",
        alembic_ini=_ROOT / "alembic.ini",
    )


def test_bootstrap_initializes_only_an_empty_database_and_returns_ready_context(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        context = bootstrap(paths, clock=_clock(), version="0.1.0")

    assert paths.db_path.is_file()
    assert paths.data_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.policy_dir.is_dir()
    with sqlite3.connect(paths.db_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0001_sqlite_schema",
        )
    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        assert context.readiness.collect().status is ReadinessStatus.READY
    context.close()


def test_bootstrap_refuses_kill_switch_before_initial_schema_mutation(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.data_dir.mkdir(parents=True)
    (paths.data_dir / "KILL").touch()

    with pytest.raises(BootstrapError, match="migration_refused") as captured:
        bootstrap(paths, clock=_clock(), version="0.1.0")

    assert captured.value.code == "migration_refused"
    assert not paths.db_path.exists()


def test_bootstrap_refuses_the_legacy_db_kill_path_without_creating_database(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    paths.db_path.parent.mkdir(parents=True)
    (paths.db_path.parent / "KILL").touch()

    with pytest.raises(BootstrapError, match="kill_path_legacy") as captured:
        bootstrap(paths, clock=_clock(), version="0.1.0")

    assert captured.value.code == "kill_path_legacy"
    assert not paths.db_path.exists()


def test_bootstrap_never_upgrades_an_existing_non_head_database(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.db_path.parent.mkdir(parents=True)
    with sqlite3.connect(paths.db_path) as connection:
        connection.execute("CREATE TABLE operator_data (value TEXT NOT NULL)")
        connection.execute("INSERT INTO operator_data VALUES ('preserve-me')")
        connection.commit()

    with (
        pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"),
        pytest.raises(BootstrapError, match="schema_not_at_head") as captured,
    ):
        bootstrap(paths, clock=_clock(), version="0.1.0")

    assert captured.value.code == "schema_not_at_head"
    with sqlite3.connect(paths.db_path) as connection:
        assert connection.execute("SELECT value FROM operator_data").fetchone() == ("preserve-me",)
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            ).fetchone()
            is None
        )


def test_bootstrap_rejects_invalid_config_without_creating_runtime_state(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    (paths.config_dir / "config.yaml").unlink()

    with pytest.raises(BootstrapError, match="config_invalid") as captured:
        bootstrap(paths, clock=_clock(), version="0.1.0")

    assert captured.value.code == "config_invalid"
    assert not paths.db_path.exists()
    assert not paths.data_dir.exists()


def test_context_close_releases_the_process_writer_for_a_clean_restart(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        first = bootstrap(paths, clock=_clock(), version="0.1.0")
    first.close()

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        second = bootstrap(paths, clock=_clock(), version="0.1.0")

    second.close()


def test_bootstrap_locates_migrations_from_the_installed_package(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    image_root = tmp_path / "image-root"
    image_root.mkdir()
    isolated_ini = image_root / "alembic.ini"
    shutil.copy2(_ROOT / "alembic.ini", isolated_ini)
    paths = replace(paths, alembic_ini=isolated_ini)

    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        context = bootstrap(paths, clock=_clock(), version="0.1.0")

    context.close()


def test_bootstrap_refuses_kill_without_mutating_a_zero_byte_database(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.data_dir.mkdir(parents=True)
    (paths.data_dir / "KILL").touch()
    paths.db_path.parent.mkdir(parents=True)
    paths.db_path.touch()

    with pytest.raises(BootstrapError, match="migration_refused"):
        bootstrap(paths, clock=_clock(), version="0.1.0")

    assert paths.db_path.stat().st_size == 0


def test_bootstrap_rejects_an_expected_head_plus_an_extra_revision(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"):
        context = bootstrap(paths, clock=_clock(), version="0.1.0")
    context.close()
    with sqlite3.connect(paths.db_path) as connection:
        connection.execute(
            "INSERT INTO alembic_version(version_num) VALUES ('unexpected_revision')"
        )
        connection.commit()

    with (
        pytest.warns(RuntimeWarning, match="unresolved paths for dry_run"),
        pytest.raises(BootstrapError, match="schema_not_at_head"),
    ):
        bootstrap(paths, clock=_clock(), version="0.1.0")
