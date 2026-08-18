from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

BUSY_TIMEOUT_MS = 5000


def connect(path: Path) -> sqlite3.Connection:
    """Open one configured SQLite connection.

    This is the single connection-policy authority: every caller receives
    foreign-key enforcement, WAL mode, the same busy timeout, and Row results.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def memory_connection() -> sqlite3.Connection:
    """Open a configured in-memory connection for schema fingerprinting."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def integrity_results(connection: sqlite3.Connection) -> tuple[str, list[sqlite3.Row]]:
    """Run SQLite's own integrity and foreign-key diagnostics."""
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    return integrity, foreign_keys


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


class SqliteUnitOfWork:
    """One explicit-commit SQLite transaction.

    Exiting without ``commit()`` rolls back even when no exception was raised.
    """

    def __init__(self, repository_or_path: Any):
        self.path = Path(getattr(repository_or_path, "path", repository_or_path))
        self.connection: sqlite3.Connection | None = None
        self._commit_requested = False

    def __enter__(self) -> SqliteUnitOfWork:
        if self.connection is not None:
            raise RuntimeError("UnitOfWork is already active")
        self.connection = connect(self.path)
        self.connection.execute("BEGIN IMMEDIATE")
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
