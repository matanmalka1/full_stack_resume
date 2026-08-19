from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self

from ...application.ports import UnitOfWork
from .connection import SqliteUnitOfWork, connect, transaction


def sqlite_unit_of_work(uow: UnitOfWork) -> SqliteUnitOfWork:
    """The UnitOfWork a SQLite repository can bind to.

    The port promises only commit/rollback, so a repository that needs the open
    connection behind it has to say so. Refusing here names the mismatch
    instead of failing later on a missing attribute.
    """
    if not isinstance(uow, SqliteUnitOfWork):
        raise TypeError("a SQLite repository binds only a SQLite UnitOfWork")
    return uow


class SqliteRepositoryBase:
    def __init__(self, path: Path, connection: Any | None = None):
        self.path = Path(path)
        self._bound_connection = connection

    def bind(self, uow: UnitOfWork) -> Self:
        sqlite_uow = sqlite_unit_of_work(uow)
        if sqlite_uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if sqlite_uow.path.resolve() != self.path.resolve():
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(self.path, sqlite_uow.connection)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        if self._bound_connection is not None:
            yield self._bound_connection
            return
        with transaction(self.path) as connection:
            yield connection

    @contextmanager
    def read_connection(self) -> Iterator[Any]:
        if self._bound_connection is not None:
            yield self._bound_connection
            return
        connection = connect(self.path)
        try:
            yield connection
        finally:
            connection.close()
