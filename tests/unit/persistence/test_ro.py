"""Read-only persistence boundary tests."""

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import OperationalError

from omra.core.errors import PersistenceError
from omra.persistence.models import Base
from omra.persistence.models.schema import PositionRow
from omra.persistence.ro import (
    close_read_only,
    init_read_only,
    make_ro_engine,
    ro_session,
)
from omra.persistence.session import make_engine


@pytest.fixture(autouse=True)
def _reset_reader() -> Iterator[None]:
    close_read_only()
    yield
    close_read_only()


def _seed_database(path: Path) -> None:
    engine = make_engine(path)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                insert(PositionRow).values(
                    account_id="acct",
                    instrument_key="KRX:278530",
                    qty=Decimal("2.00"),
                    avg_cost=Decimal("10000"),
                    updated_at="2026-08-19T01:00:00+00:00",
                )
            )
    finally:
        engine.dispose()


def test_ro_engine_uses_uri_mode_and_query_only(tmp_path: Path) -> None:
    path = tmp_path / "reader.sqlite"
    _seed_database(path)
    engine = make_ro_engine(path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
            assert connection.scalar(select(PositionRow.qty)) == Decimal("2.00")
            with pytest.raises(OperationalError, match=r"readonly|read-only"):
                connection.execute(
                    insert(PositionRow).values(
                        account_id="other",
                        instrument_key="KRX:123456",
                        qty=Decimal("1"),
                        avg_cost=Decimal("1"),
                        updated_at="2026-08-19T01:00:00+00:00",
                    )
                )
    finally:
        engine.dispose()


def test_ro_session_blocks_orm_flush(tmp_path: Path) -> None:
    path = tmp_path / "reader.sqlite"
    _seed_database(path)
    init_read_only(path)

    with ro_session() as session:
        session.add(
            PositionRow(
                account_id="other",
                instrument_key="KRX:123456",
                qty=Decimal("1"),
                avg_cost=Decimal("1"),
                updated_at="2026-08-19T01:00:00+00:00",
            )
        )
        with pytest.raises(RuntimeError, match="cannot flush"):
            session.flush()


def test_ro_session_reads_without_autoflush(tmp_path: Path) -> None:
    path = tmp_path / "reader.sqlite"
    _seed_database(path)
    init_read_only(path)

    with ro_session() as session:
        assert session.scalar(select(PositionRow.qty)) == Decimal("2.00")


def test_uninitialized_and_duplicate_ro_initialization_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(PersistenceError, match="not initialized"), ro_session():
        pass

    path = tmp_path / "reader.sqlite"
    _seed_database(path)
    init_read_only(path)
    with pytest.raises(PersistenceError, match="already initialized"):
        init_read_only(path)
