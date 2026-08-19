"""Fail-closed composition root for the M0 container runtime shell."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from omra.config import ConfigError, load_and_validate_config
from omra.monitoring.readiness import ReadinessProbe
from omra.persistence.session import close_persistence, init_persistence

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from omra.config import ConfigBundle
    from omra.core import Clock


class BootstrapError(RuntimeError):
    """A bounded startup failure safe to expose to an operator."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Explicit host/container paths needed by the M0 process."""

    config_dir: Path
    db_path: Path
    data_dir: Path
    logs_dir: Path
    policy_dir: Path
    alembic_ini: Path

    @property
    def writable_dirs(self) -> tuple[Path, ...]:
        """Return the only persistent directories the app may mutate."""
        return (self.db_path.parent, self.data_dir, self.logs_dir, self.policy_dir)


@dataclass(frozen=True, slots=True)
class BootstrapContext:
    """Resources that stay live for the duration of the ASGI process."""

    config: ConfigBundle
    engine: Engine
    readiness: ReadinessProbe

    def close(self) -> None:
        """Dispose the process-local writer engine."""
        close_persistence()


def _alembic_config(paths: RuntimePaths) -> Config:
    configuration = Config(str(paths.alembic_ini))
    script_location = Path(__file__).resolve().parents[1] / "persistence" / "migrations"
    configuration.set_main_option("script_location", str(script_location))
    configuration.set_main_option("sqlalchemy.url", f"sqlite:///{paths.db_path}")
    return configuration


def _expected_revision(configuration: Config) -> str:
    revision = ScriptDirectory.from_config(configuration).get_current_head()
    if revision is None:
        raise BootstrapError("migration_head_missing")
    return revision


def _current_revisions(db_path: Path) -> tuple[str, ...] | None:
    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    except (OSError, sqlite3.Error):
        return None
    return tuple(str(row[0]) for row in rows)


def _kill_path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise BootstrapError("kill_state_unavailable") from error
    return True


def _refuse_kill_switch(paths: RuntimePaths) -> None:
    if _kill_path_exists(paths.data_dir / "KILL"):
        raise BootstrapError("migration_refused")
    legacy_path = paths.db_path.parent / "KILL"
    if _kill_path_exists(legacy_path):
        raise BootstrapError("kill_path_legacy")


def _create_runtime_dirs(paths: RuntimePaths) -> None:
    try:
        for directory in paths.writable_dirs:
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise BootstrapError("runtime_path_unavailable") from error


def _initialize_or_verify_schema(paths: RuntimePaths) -> str:
    configuration = _alembic_config(paths)
    expected_revision = _expected_revision(configuration)
    try:
        initialize = paths.db_path.stat().st_size == 0
    except FileNotFoundError:
        initialize = True
    except OSError as error:
        raise BootstrapError("database_path_unavailable") from error
    if initialize:
        try:
            command.upgrade(configuration, "head")
        except SystemExit as error:
            raise BootstrapError("migration_refused") from error
        except Exception as error:
            raise BootstrapError("migration_failed") from error
    if _current_revisions(paths.db_path) != (expected_revision,):
        raise BootstrapError("schema_not_at_head")
    return expected_revision


def bootstrap(
    paths: RuntimePaths,
    clock: Clock,
    version: str,
) -> BootstrapContext:
    """Validate config, initialize only an empty DB, and bind the writer once."""
    _refuse_kill_switch(paths)
    try:
        bundle = load_and_validate_config(paths.config_dir, clock=clock)
    except (ConfigError, OSError) as error:
        raise BootstrapError("config_invalid") from error

    _create_runtime_dirs(paths)
    expected_revision = _initialize_or_verify_schema(paths)
    try:
        engine = init_persistence(paths.db_path)
    except Exception as error:
        close_persistence()
        raise BootstrapError("persistence_unavailable") from error

    readiness = ReadinessProbe(
        config_dir=paths.config_dir,
        db_path=paths.db_path,
        writable_dirs=paths.writable_dirs,
        expected_revision=expected_revision,
        clock=clock,
        version=version,
    )
    return BootstrapContext(config=bundle, engine=engine, readiness=readiness)


__all__ = ["BootstrapContext", "BootstrapError", "RuntimePaths", "bootstrap"]
