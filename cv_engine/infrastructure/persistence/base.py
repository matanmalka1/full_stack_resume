from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from .connection import SqliteUnitOfWork, connect, transaction

TRepository = TypeVar("TRepository", bound="SqliteRepositoryBase")


class SqliteRepositoryBase:
    def __init__(self, path: Path, connection: Any | None = None):
        self.path = Path(path)
        self._bound_connection = connection

    def bind(self: TRepository, uow: SqliteUnitOfWork) -> TRepository:
        if uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if uow.path.resolve() != self.path.resolve():
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(self.path, uow.connection)

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
