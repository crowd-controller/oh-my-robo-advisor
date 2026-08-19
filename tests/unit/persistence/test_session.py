"""Single-writer engine and transaction-boundary tests."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from sqlite3 import OperationalError as SQLiteOperationalError
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import omra.persistence.session as session_module
from omra.core.errors import PersistenceError
from omra.persistence.models import Base
from omra.persistence.models.schema import FillRow, PositionRow
from omra.persistence.session import (
    BUSY_MAX_ATTEMPTS,
    close_persistence,
    init_persistence,
    make_engine,
    write_session,
)

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPICursor


@pytest.fixture(autouse=True)
def _reset_writer() -> Iterator[None]:
    close_persistence()
    yield
    close_persistence()


def test_writer_connection_enforces_all_sqlite_pragmas(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "writer.sqlite")
    try:
        with engine.connect() as connection:
            actual = {
                name: connection.exec_driver_sql(f"PRAGMA {name}").scalar_one()
                for name in ("journal_mode", "busy_timeout", "synchronous", "foreign_keys")
            }
    finally:
        engine.dispose()

    assert actual == {
        "journal_mode": "wal",
        "busy_timeout": 5000,
        "synchronous": 1,
        "foreign_keys": 1,
    }


def test_write_session_commits_one_short_unit_of_work(tmp_path: Path) -> None:
    engine = init_persistence(tmp_path / "writer.sqlite")
    Base.metadata.create_all(engine)

    with write_session() as session:
        session.add(
            PositionRow(
                account_id="acct",
                instrument_key="KRX:278530",
                qty=Decimal("1.2500"),
                avg_cost=Decimal("12345.00"),
                updated_at="2026-08-19T01:00:00+00:00",
            )
        )

    with write_session() as session:
        row = session.get(PositionRow, ("acct", "KRX:278530"))

    assert row is not None
    assert row.qty == Decimal("1.2500")
    assert row.avg_cost == Decimal("12345.00")


def _write_then_abort() -> None:
    with write_session() as session:
        session.add(
            PositionRow(
                account_id="acct",
                instrument_key="KRX:278530",
                qty=Decimal("1"),
                avg_cost=Decimal("10000"),
                updated_at="2026-08-19T01:00:00+00:00",
            )
        )
        raise RuntimeError("abort unit")


def test_write_session_rolls_back_and_reraises(tmp_path: Path) -> None:
    engine = init_persistence(tmp_path / "writer.sqlite")
    Base.metadata.create_all(engine)

    with pytest.raises(RuntimeError, match="abort unit"):
        _write_then_abort()

    with write_session() as session:
        count = session.scalar(select(func.count()).select_from(PositionRow))

    assert count == 0


def test_foreign_keys_are_enforced_through_writer_sessions(tmp_path: Path) -> None:
    engine = init_persistence(tmp_path / "writer.sqlite")
    Base.metadata.create_all(engine)

    with pytest.raises(IntegrityError), write_session() as session:
        session.add(
            FillRow(
                id="01INVALIDFILL0000000000000",
                order_id="missing-order",
                qty=Decimal("1"),
                price=Decimal("100"),
                fee=None,
                tax=None,
                filled_at_kst=datetime(2026, 8, 19, 10, 0, tzinfo=UTC),
                settle_date="2026-08-21",
                broker_exec_id="exec-1",
            )
        )


def test_uninitialized_and_duplicate_initialization_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(PersistenceError, match="not initialized"), write_session():
        pass

    init_persistence(tmp_path / "writer.sqlite")
    with pytest.raises(PersistenceError, match="already initialized"):
        init_persistence(tmp_path / "other.sqlite")


class _BusyCursor:
    def __init__(self, failures: int, message: str = "database is locked") -> None:
        self.failures = failures
        self.message = message
        self.calls = 0

    def execute(self, statement: str, parameters: object) -> None:
        del statement, parameters
        self.calls += 1
        if self.calls <= self.failures:
            raise SQLiteOperationalError(self.message)


def test_sqlite_busy_retries_the_same_statement_up_to_three_attempts() -> None:
    cursor = _BusyCursor(failures=2)

    handled = session_module._execute_with_busy_retry(
        cast("DBAPICursor", cursor), "SELECT 1", (), None
    )

    assert handled is True
    assert cursor.calls == BUSY_MAX_ATTEMPTS


def test_sqlite_busy_reraises_after_the_third_failed_attempt() -> None:
    cursor = _BusyCursor(failures=BUSY_MAX_ATTEMPTS)

    with pytest.raises(SQLiteOperationalError, match="database is locked"):
        session_module._execute_with_busy_retry(cast("DBAPICursor", cursor), "SELECT 1", (), None)

    assert cursor.calls == BUSY_MAX_ATTEMPTS


def test_non_busy_operational_error_is_not_retried() -> None:
    cursor = _BusyCursor(failures=1, message="no such table")

    with pytest.raises(SQLiteOperationalError, match="no such table"):
        session_module._execute_with_busy_retry(cast("DBAPICursor", cursor), "SELECT 1", (), None)

    assert cursor.calls == 1
