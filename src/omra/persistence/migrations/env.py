"""Alembic environment with migration safety guards."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool
from sqlalchemy.engine import make_url

from omra.persistence.models import Base
from omra.persistence.types import DecimalText, KSTDateTimeText

if TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _render_item(
    kind: str,
    item: Any,
    autogen_context: AutogenContext,
) -> str | Literal[False]:
    del autogen_context
    if kind == "type" and isinstance(item, (DecimalText, KSTDateTimeText)):
        return "sa.Text()"
    return False


def _database_path() -> Path:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url is None:
        raise SystemExit("sqlalchemy.url is required for guarded migrations")
    database = make_url(configured_url).database
    if database is None or database == ":memory:":
        raise SystemExit("file-backed SQLite is required for guarded migrations")
    if database.startswith("file:"):
        database = database.removeprefix("file:")
    return Path(database)


def _kill_path_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise SystemExit("KILL switch state unavailable — migration refused") from error
    return True


def _guard_kill_paths(db_dir: Path) -> None:
    kill_path = db_dir.parent / "data" / "KILL"
    if _kill_path_present(kill_path):
        raise SystemExit("KILL switch present — migration refused (01 §1.3)")

    legacy_kill_path = db_dir / "KILL"
    if _kill_path_present(legacy_kill_path):
        raise SystemExit("legacy KILL path present — migration refused; move it to data/KILL")


def _guard_stopped(connection: Connection) -> None:
    has_bot_state = connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bot_state'"
    ).scalar()
    if not has_bot_state:
        return

    state = connection.exec_driver_sql("SELECT state FROM bot_state WHERE id=1").scalar()
    if state == "STOPPED":
        raise SystemExit("BotState=STOPPED — migration refused (01 §1.3)")


def run_migrations_offline() -> None:
    """Render SQL without mutating a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run guarded migrations against one file-backed SQLite database."""
    database_path = _database_path()
    _guard_kill_paths(database_path.parent)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA busy_timeout=5000")
        connection.exec_driver_sql("PRAGMA synchronous=NORMAL")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        _guard_stopped(connection)
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
