"""The database-held lock that makes the Operation worker the only one.

Not a persistence adapter: it owns a dedicated connection for the worker's whole
life, which adapters never do. Like the transaction manager, it is connection-owning
infrastructure and is exempt from the adapter contract for that reason.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from ...application.operation_runner import WorkerAlreadyRunning

#: The session advisory lock the running worker holds for its whole life.
WORKER_LOCK_KEY = 0x63765F776F726B  # "cv_work"


class _AdvisoryWorkerLock:
    """The dedicated session that holds the worker lock, and whether it still does."""

    def __init__(self, connection: Connection):
        self._connection = connection

    def held(self) -> bool:
        """True while the lock session is alive.

        A session advisory lock lasts exactly as long as its session, so a
        live session is a held lock. A terminated or disconnected session has
        already released it, and any error reaching the session means the same.
        """
        try:
            self._connection.execute(text("SELECT 1"))
            self._connection.commit()
        except DBAPIError:
            return False
        return True


@contextmanager
def worker_exclusivity(engine: Engine) -> Iterator[_AdvisoryWorkerLock]:
    """Hold the database's single worker slot while the block runs.

    Worker startup interrupts every claimed Operation, which is only safe when
    no other worker is alive. A PostgreSQL session advisory lock makes that a
    mechanism rather than a convention: a second worker is refused at start
    instead of interrupting the first one's live work. The lock lives on a
    dedicated connection that is discarded afterwards, never returned to the
    pool, so a crash or an early exit releases it with the session.

    The session can also end underneath a live worker (terminated, or the
    server restarted). The yielded lock answers `held()` so the worker can stop
    as soon as it notices, instead of running on without exclusivity.
    """
    connection = engine.connect()
    try:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK_KEY}
        ).scalar_one()
        connection.commit()
        if not acquired:
            raise WorkerAlreadyRunning("another Operation worker is already running")
        yield _AdvisoryWorkerLock(connection)
    finally:
        connection.invalidate()
        connection.close()
