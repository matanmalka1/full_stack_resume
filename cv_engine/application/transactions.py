"""Transaction-lifetime policy shared by persistence and outbound adapters."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from .ports.transactions import ReadTransaction

_active_transaction: ContextVar[ReadTransaction | None] = ContextVar(
    "cv_engine_active_transaction", default=None
)


def begin_transaction_scope(transaction: ReadTransaction) -> Token[ReadTransaction | None]:
    """Mark one transaction active and refuse nesting in the current execution context."""
    if _active_transaction.get() is not None:
        raise RuntimeError("nested database transactions are forbidden")
    return _active_transaction.set(transaction)


def end_transaction_scope(token: Token[ReadTransaction | None]) -> None:
    _active_transaction.reset(token)


def transaction_is_active() -> bool:
    return _active_transaction.get() is not None


def assert_external_io_allowed(operation: str = "external I/O") -> None:
    """Refuse an external side effect while a database transaction is active."""
    if transaction_is_active():
        raise RuntimeError(f"{operation} is forbidden while a database transaction is active")


def active_transaction_for_tests() -> Any:
    """Expose no production capability; allow architecture tests to inspect scope cleanup."""
    return _active_transaction.get()
