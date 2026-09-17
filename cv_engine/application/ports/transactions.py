"""Application-owned database transaction boundaries.

The tokens deliberately expose no connection and no commit operation.  A use-case owns the
scope; the infrastructure manager owns the driver transaction and commits a write scope exactly
once when it exits successfully.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol


class TransactionConflict(RuntimeError):
    """A concurrent write requires replaying the command in a fresh scope."""


class ReadTransaction(Protocol):
    """Opaque token proving that a database transaction is currently active."""

    @property
    def active(self) -> bool: ...


class WriteTransaction(ReadTransaction, Protocol):
    """Opaque token accepted by persistence methods that mutate stored state."""

    @property
    def writable(self) -> bool: ...


class TransactionManager(Protocol):
    """Open one non-nestable transaction scope over the configured database."""

    def read(self) -> AbstractContextManager[ReadTransaction]: ...

    def write(self) -> AbstractContextManager[WriteTransaction]: ...
