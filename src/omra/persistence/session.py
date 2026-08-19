"""Single-writer SQLAlchemy engine and short transaction boundary."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import OperationalError as SQLiteOperationalError
from typing import Any, Final, Literal

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine import ExecutionContext
from sqlalchemy.engine.interfaces import DBAPIConnection, DBAPICursor
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from omra.core.errors import PersistenceError

BUSY_MAX_ATTEMPTS: Final = 3
BUSY_RETRY_WAIT_SECONDS: Final = 0.05

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _is_sqlite_busy(error: BaseException) -> bool:
    return isinstance(error, SQLiteOperationalError) and "locked" in str(error).lower()


def _execute_with_busy_retry(
    cursor: DBAPICursor,
    statement: str,
    parameters: Any,
    context: ExecutionContext | None,
) -> Literal[True]:
    del context
    retrying = Retrying(
        retry=retry_if_exception(_is_sqlite_busy),
        stop=stop_after_attempt(BUSY_MAX_ATTEMPTS),
        wait=wait_fixed(BUSY_RETRY_WAIT_SECONDS),
        reraise=True,
    )
    for attempt in retrying:
        with attempt:
            cursor.execute(statement, parameters)
    return True


def _install_connection_policy(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(
        dbapi_connection: DBAPIConnection,
        connection_record: ConnectionPoolEntry,
    ) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    event.listen(engine, "do_execute", _execute_with_busy_retry, retval=True)


def make_engine(db_path: Path) -> Engine:
    """Create the process-local SQLite writer engine."""
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(db_path)),
        connect_args={"timeout": 5.0},
        pool_pre_ping=False,
    )
    _install_connection_policy(engine)
    return engine


def init_persistence(db_path: Path) -> Engine:
    """Bind the singleton writer session factory once for this process."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        raise PersistenceError("writer persistence is already initialized")
    engine = make_engine(db_path)
    _engine = engine
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def close_persistence() -> None:
    """Dispose the writer engine during orderly process shutdown."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def write_session() -> Iterator[Session]:
    """Commit one short unit of work, rolling back and re-raising on failure."""
    if _session_factory is None:
        raise PersistenceError("writer persistence is not initialized")

    session = _session_factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "BUSY_MAX_ATTEMPTS",
    "close_persistence",
    "init_persistence",
    "make_engine",
    "write_session",
]
