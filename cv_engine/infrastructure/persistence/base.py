from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Self

from sqlalchemy.engine import Connection, Engine

from ...application.ports import UnitOfWork
from .connection import SqlAlchemyUnitOfWork


def sqlalchemy_unit_of_work(uow: UnitOfWork) -> SqlAlchemyUnitOfWork:
    """Return the concrete UnitOfWork a SQLAlchemy repository can bind to.

    The port promises only commit/rollback, so a repository that needs the open
    connection behind it has to say so. Refusing here names the mismatch
    instead of failing later on a missing attribute.
    """
    if not isinstance(uow, SqlAlchemyUnitOfWork):
        raise TypeError("a SQLAlchemy repository binds only a SQLAlchemy UnitOfWork")
    return uow


class SqlAlchemyRepositoryBase:
    def __init__(self, engine: Engine, connection: Connection | None = None):
        self.engine = engine
        self._bound_connection = connection

    def bind(self, uow: UnitOfWork) -> Self:
        sqlalchemy_uow = sqlalchemy_unit_of_work(uow)
        if sqlalchemy_uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if sqlalchemy_uow.engine is not self.engine:
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(self.engine, sqlalchemy_uow.connection)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        if self._bound_connection is not None:
            yield self._bound_connection
            return
        with self.engine.begin() as connection:
            yield connection

    @contextmanager
    def read_connection(self) -> Iterator[Connection]:
        if self._bound_connection is not None:
            yield self._bound_connection
            return
        with self.engine.connect() as connection:
            yield connection

    @contextmanager
    def read_transaction(self) -> Iterator[Self]:
        """Bind every query in one projection to one consistent snapshot."""
        if self._bound_connection is not None:
            yield self
            return
        connection = self.engine.connect().execution_options(isolation_level="REPEATABLE READ")
        transaction = connection.begin()
        try:
            yield type(self)(self.engine, connection)
        finally:
            transaction.rollback()
            connection.close()
