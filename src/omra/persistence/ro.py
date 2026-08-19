"""Read-only SQLAlchemy engine protected at URI, SQLite, and ORM layers."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from omra.core.errors import PersistenceError

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


class ReadOnlySession(Session):
    """Session class whose ORM unit of work can never flush."""


@event.listens_for(ReadOnlySession, "before_flush")
def _reject_flush(session: Session, flush_context: object, instances: object) -> None:
    del session, flush_context, instances
    raise RuntimeError("read-only session cannot flush")


@event.listens_for(ReadOnlySession, "do_orm_execute")
def _reject_orm_dml(execute_state: ORMExecuteState) -> None:
    if not execute_state.is_select:
        raise RuntimeError("read-only session cannot execute ORM DML")


def make_ro_engine(db_path: Path) -> Engine:
    """Create a SQLite engine opened with URI mode=ro and query_only."""
    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=f"file:{db_path}",
            query={"mode": "ro", "uri": "true"},
        ),
        connect_args={"timeout": 5.0},
        pool_pre_ping=False,
    )

    @event.listens_for(engine, "connect")
    def _set_query_only(
        dbapi_connection: DBAPIConnection,
        connection_record: ConnectionPoolEntry,
    ) -> None:
        del connection_record
        dbapi_connection.execute("PRAGMA query_only=ON")

    return engine


def init_read_only(db_path: Path) -> Engine:
    """Bind the singleton read-only session factory once for this process."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        raise PersistenceError("read-only persistence is already initialized")
    engine = make_ro_engine(db_path)
    _engine = engine
    _session_factory = sessionmaker(
        bind=engine,
        class_=ReadOnlySession,
        autoflush=False,
        expire_on_commit=False,
    )
    return engine


def close_read_only() -> None:
    """Dispose the read-only engine during orderly process shutdown."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def ro_session() -> Iterator[Session]:
    """Yield a non-flushing session and always release its read transaction."""
    if _session_factory is None:
        raise PersistenceError("read-only persistence is not initialized")

    session = _session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


__all__ = [
    "ReadOnlySession",
    "close_read_only",
    "init_read_only",
    "make_ro_engine",
    "ro_session",
]
