"""Initial Alembic revision and migration safety tests."""

import re
import sqlite3
from pathlib import Path
from typing import Final

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from omra.persistence.models import TABLE_NAMES, Base

_ROOT: Final = Path(__file__).resolve().parents[3]
_SCRIPT_LOCATION: Final = _ROOT / "src" / "omra" / "persistence" / "migrations"
_REVISION: Final = "0001_sqlite_schema"
_INDEX_NAMES: Final[frozenset[str]] = frozenset(
    {
        "ix_approvals_open",
        "ix_decomp_meta_asof",
        "ix_experiments_hash",
        "ix_expev_exp",
        "ix_fills_order",
        "ix_fills_settle",
        "ix_orders_intent",
        "ix_orders_netbuy",
        "ix_orders_open",
        "ix_orders_orphan",
        "ix_orders_plan",
        "ix_plans_asof",
        "ix_prot_tripped",
        "ix_reconcile_open",
        "ix_research_verdict",
        "ix_survflags_active",
        "ix_taxev_year",
        "ix_unmatched_open",
        "ux_reconcile_idem",
    }
)
_TRIGGER_NAMES: Final[frozenset[str]] = frozenset(
    {
        "trg_experiments_no_delete",
        "trg_experiments_no_update",
        "trg_expev_no_delete",
        "trg_expev_no_update",
    }
)


def _database_path(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime" / "var"
    (runtime / "db").mkdir(parents=True)
    (runtime / "data").mkdir()
    return runtime / "db" / "omra.sqlite"


def _config(database_path: Path) -> Config:
    configuration = Config(str(_ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(_SCRIPT_LOCATION))
    configuration.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    return configuration


def _upgrade(tmp_path: Path) -> tuple[Path, Config]:
    database_path = _database_path(tmp_path)
    configuration = _config(database_path)
    command.upgrade(configuration, "head")
    return database_path, configuration


def _user_tables(connection: sqlite3.Connection) -> frozenset[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
    )
    return frozenset(row[0] for row in rows)


def _named_schema_objects(
    connection: sqlite3.Connection, object_type: str
) -> dict[str, tuple[str, str]]:
    rows = connection.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master "
        "WHERE type = ? AND sql IS NOT NULL ORDER BY name",
        (object_type,),
    )
    return {
        name: (table_name, " ".join(sql.casefold().split()))
        for name, table_name, sql in rows
        if not name.startswith("sqlite_")
    }


def _table_signature(connection: sqlite3.Connection, table_name: str) -> tuple[object, ...]:
    table_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    assert table_sql_row is not None
    table_sql = table_sql_row[0]
    constraint_names = tuple(sorted(re.findall(r"CONSTRAINT ([A-Za-z0-9_]+)", table_sql)))
    columns = tuple(connection.execute(f'PRAGMA table_info("{table_name}")'))
    foreign_keys = tuple(sorted(connection.execute(f'PRAGMA foreign_key_list("{table_name}")')))
    return columns, foreign_keys, constraint_names


def test_initial_revision_is_the_only_head_and_has_no_parent(tmp_path: Path) -> None:
    database_path = _database_path(tmp_path)
    scripts = ScriptDirectory.from_config(_config(database_path))
    revisions = list(scripts.walk_revisions())

    assert scripts.get_heads() == [_REVISION]
    assert len(revisions) == 1
    assert revisions[0].revision == _REVISION
    assert revisions[0].down_revision is None


def test_initial_upgrade_matches_metadata_and_has_all_physical_objects(tmp_path: Path) -> None:
    database_path, configuration = _upgrade(tmp_path)
    metadata_path = tmp_path / "metadata.sqlite"
    metadata_engine = create_engine(f"sqlite:///{metadata_path}")
    try:
        Base.metadata.create_all(metadata_engine)
    finally:
        metadata_engine.dispose()

    with sqlite3.connect(database_path) as migrated, sqlite3.connect(metadata_path) as metadata:
        assert _user_tables(migrated) == TABLE_NAMES
        assert len(_user_tables(migrated)) == 34
        assert {
            name for name in _named_schema_objects(migrated, "index") if name in _INDEX_NAMES
        } == _INDEX_NAMES
        assert set(_named_schema_objects(migrated, "trigger")) == _TRIGGER_NAMES
        assert migrated.execute("SELECT version_num FROM alembic_version").fetchone() == (
            _REVISION,
        )

        for table_name in TABLE_NAMES:
            assert _table_signature(migrated, table_name) == _table_signature(metadata, table_name)

        migrated_indexes = _named_schema_objects(migrated, "index")
        metadata_indexes = _named_schema_objects(metadata, "index")
        assert {name: migrated_indexes[name] for name in _INDEX_NAMES} == {
            name: metadata_indexes[name] for name in _INDEX_NAMES
        }

    command.check(configuration)


def test_append_only_triggers_reject_update_and_delete(tmp_path: Path) -> None:
    database_path, _ = _upgrade(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "exp-1",
                "hash-1",
                None,
                None,
                None,
                None,
                "2026-01-01",
                "2026-08-19",
                "2026-08-19T00:00:00Z",
                "tester",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?)",
            ("event-1", "exp-1", "registered", "{}", "2026-08-19T00:00:00Z"),
        )
        connection.commit()

        for statement in (
            "UPDATE experiments SET payload_json='[]' WHERE experiment_id='exp-1'",
            "DELETE FROM experiments WHERE experiment_id='exp-1'",
            "UPDATE experiment_events SET payload_json='[]' WHERE id='event-1'",
            "DELETE FROM experiment_events WHERE id='event-1'",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(statement)


def test_reconcile_expression_index_treats_null_instrument_as_one_key(tmp_path: Path) -> None:
    database_path, _ = _upgrade(tmp_path)
    statement = (
        "INSERT INTO reconcile_expectations "
        "(id, account_id, kind, instrument_key, expected_date_from, expected_date_to, "
        "amount_tolerance, source, expires_at, created_at) "
        "VALUES (?, 'acct', 'cash_in', NULL, '2026-08-19', '2026-08-19', 1, "
        "'system', '2026-08-20', '2026-08-19T00:00:00Z')"
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(statement, ("expected-1",))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(statement, ("expected-2",))


def test_kill_switch_refuses_migration_before_schema_mutation(tmp_path: Path) -> None:
    database_path = _database_path(tmp_path)
    database_path.parent.parent.joinpath("data", "KILL").touch()

    with pytest.raises(SystemExit, match="KILL switch present"):
        command.upgrade(_config(database_path), "head")

    assert not database_path.exists()


def test_legacy_db_kill_path_refuses_direct_migration_before_schema_mutation(
    tmp_path: Path,
) -> None:
    database_path = _database_path(tmp_path)
    (database_path.parent / "KILL").touch()

    with pytest.raises(SystemExit, match="legacy KILL path present"):
        command.upgrade(_config(database_path), "head")

    assert not database_path.exists()


def test_stopped_bot_state_refuses_subsequent_migration_command(tmp_path: Path) -> None:
    database_path, configuration = _upgrade(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO bot_state (id, state, since) VALUES (1, 'STOPPED', '2026-08-19')"
        )
        connection.commit()

    with pytest.raises(SystemExit, match="BotState=STOPPED"):
        command.upgrade(configuration, "head")


def test_downgrade_is_explicitly_unsupported(tmp_path: Path) -> None:
    database_path, configuration = _upgrade(tmp_path)

    with pytest.raises(NotImplementedError, match="restore via Litestream"):
        command.downgrade(configuration, "base")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            _REVISION,
        )
        assert _user_tables(connection) == TABLE_NAMES
