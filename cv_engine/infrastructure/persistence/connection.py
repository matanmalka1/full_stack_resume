from __future__ import annotations

from contextlib import AbstractContextManager
from contextvars import Token
from functools import cache
from typing import Any, Literal, cast

from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from ...application.ports.transactions import ReadTransaction, TransactionConflict, WriteTransaction
from ...application.transactions import (
    begin_transaction_scope,
    end_transaction_scope,
    transaction_is_active,
)


@cache
def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def current_database_revision(engine: Engine) -> str | None:
    """Return the revision recorded by Alembic, or ``None`` before migration."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


class SqlAlchemyTransaction:
    """Opaque application token backed by one SQLAlchemy connection."""

    def __init__(
        self,
        *,
        manager: SqlAlchemyTransactionManager,
        connection: Connection,
        writable: bool,
    ):
        self._manager = manager
        self._connection = connection
        self._writable = writable
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    @property
    def writable(self) -> bool:
        return self._writable

    def _close(self) -> None:
        self._active = False


class _SqlAlchemyTransactionScope(AbstractContextManager[SqlAlchemyTransaction]):
    def __init__(self, manager: SqlAlchemyTransactionManager, *, writable: bool):
        self._manager = manager
        self._writable = writable
        self._transaction: SqlAlchemyTransaction | None = None
        self._scope_token: Token[ReadTransaction | None] | None = None
        self._used = False

    def __enter__(self) -> SqlAlchemyTransaction:
        if self._used:
            raise RuntimeError("transaction scope cannot be reused")
        if transaction_is_active():
            raise RuntimeError("nested database transactions are forbidden")
        self._used = True
        connection = self._manager.engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        )
        try:
            connection.begin()
            transaction = SqlAlchemyTransaction(
                manager=self._manager,
                connection=connection,
                writable=self._writable,
            )
            scope_token = begin_transaction_scope(transaction)
        except BaseException:
            connection.close()
            raise
        self._transaction = transaction
        self._scope_token = scope_token
        return transaction

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None:
        transaction = self._transaction
        scope_token = self._scope_token
        if transaction is None or scope_token is None:
            return None
        connection = transaction._connection
        try:
            if exc_type is None and self._writable:
                connection.commit()
            else:
                connection.rollback()
        except BaseException as error:
            if connection.in_transaction():
                connection.rollback()
            if isinstance(error, DBAPIError) and getattr(error.orig, "sqlstate", None) == "40001":
                raise TransactionConflict("concurrent database update") from error
            raise
        finally:
            transaction._close()
            connection.close()
            end_transaction_scope(scope_token)
            self._transaction = None
            self._scope_token = None
        if isinstance(exc, DBAPIError) and getattr(exc.orig, "sqlstate", None) == "40001":
            raise TransactionConflict("concurrent database update") from exc
        return None


class SqlAlchemyTransactionManager:
    """Create auto-closing read and write scopes for exactly one Engine."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def read(self) -> AbstractContextManager[ReadTransaction]:
        return cast(
            AbstractContextManager[ReadTransaction],
            _SqlAlchemyTransactionScope(self, writable=False),
        )

    def write(self) -> AbstractContextManager[WriteTransaction]:
        return cast(
            AbstractContextManager[WriteTransaction],
            _SqlAlchemyTransactionScope(self, writable=True),
        )

    def connection_for(
        self,
        transaction: ReadTransaction,
        *,
        access: Literal["read", "write"] = "read",
    ) -> Connection:
        """Resolve a valid token without letting repositories retain the connection."""
        if not isinstance(transaction, SqlAlchemyTransaction):
            raise TypeError("SQLAlchemy persistence requires a SQLAlchemy transaction")
        if transaction._manager is not self:
            raise TypeError("transaction belongs to another transaction manager")
        if not transaction.active:
            raise RuntimeError("transaction is closed")
        if access == "write" and not transaction.writable:
            raise TypeError("a write requires an active write transaction")
        return transaction._connection
