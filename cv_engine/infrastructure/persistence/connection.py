from __future__ import annotations

from functools import cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection


@cache
def create_database_engine(database_url: str) -> Engine:
    """Build the application's configured database engine.

    This remains the single connection-policy authority: repositories and
    units of work for one URL share the same pool and connection health policy.
    An Engine is process-wide infrastructure, not per-service state; caching it
    also prevents repeated CLI/service composition from accumulating idle
    PostgreSQL pools.
    """
    return create_engine(database_url, pool_pre_ping=True)


def _engine_for(repository_or_engine: Any) -> Engine:
    engine = getattr(repository_or_engine, "engine", repository_or_engine)
    if not isinstance(engine, Engine):
        raise TypeError("UnitOfWork requires a SQLAlchemy Engine or repository")
    return engine


class SqlAlchemyUnitOfWork:
    """One explicit-commit SQLAlchemy transaction.

    Exiting without ``commit()`` rolls back even when no exception was raised.
    REPEATABLE READ also gives a bound multi-query projection one stable
    snapshot for the lifetime of the unit of work.
    """

    def __init__(self, repository_or_engine: Any):
        self.engine = _engine_for(repository_or_engine)
        self.connection: Connection | None = None
        self._commit_requested = False

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self.connection is not None:
            raise RuntimeError("UnitOfWork is already active")
        self.connection = self.engine.connect().execution_options(isolation_level="REPEATABLE READ")
        self.connection.begin()
        self._commit_requested = False
        return self

    def __exit__(self, *exc: Any) -> bool | None:
        if self.connection is None:
            return None
        try:
            if exc[0] is None and self._commit_requested:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
            self.connection = None
            self._commit_requested = False
        return None

    def commit(self) -> None:
        if self.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        self._commit_requested = True

    def rollback(self) -> None:
        if self.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        self.connection.rollback()
        self._commit_requested = False
