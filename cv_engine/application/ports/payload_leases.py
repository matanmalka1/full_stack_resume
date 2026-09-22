"""Write-lease coordination for immutable payload storage (architecture.md §7.1).

A lease reserves a *group key* - one immutable payload, or the small file set
one registration depends on - before any bytes are written, under physical
keys scoped to that specific attempt. Registration is gated on the lease
still matching the attempt trying to commit; safe deletion of an abandoned
attempt is gated on fencing it first. Nothing here performs the payload I/O
itself - that stays with `SnapshotPayloadStore`/`RevisionPayloadStore` - this
port only coordinates *when* a write is safe to register or safe to remove.
"""

from __future__ import annotations

from typing import Protocol

from ..errors import StateConflict  # noqa: F401  (documents what acquire/mark_committed raise)
from .transactions import ReadTransaction, WriteTransaction

#: Default bound for a single-file write (snapshot, draft snapshot, provider
#: response): a plain bytes-to-storage write with no external dependency, so a
#: TTL far longer than any realistic write is a comfortable, low-risk margin
#: rather than a tight timing assumption.
DEFAULT_LEASE_TTL_SECONDS = 300

#: Bound for a render attempt, which drives an external browser process and so
#: can legitimately run longer than an ordinary write.
RENDER_LEASE_TTL_SECONDS = 900

#: Bound on how long a fenced lease may sit in `reclaiming` before a later
#: `reclaim_orphans` call treats it as interrupted and resumes it.
RECLAIM_GRACE_SECONDS = 120


class PayloadWriteLeaseStore(Protocol):
    """Adapter for the `payload_write_leases` table."""

    def acquire(
        self,
        tx: WriteTransaction,
        group_key: str,
        attempt_id: str,
        *,
        keys: list[str],
        ttl_seconds: int,
        now: str | None = None,
    ) -> None:
        """Claim `group_key` for a new attempt, in `pending` state.

        Raises `StateConflict` if any row - pending, reclaiming, or committed -
        already exists for this group key. Only `reclaim_orphans` removes a
        row; acquire never overwrites one.
        """
        ...

    def release(self, tx: WriteTransaction, group_key: str, attempt_id: str) -> None:
        """Remove a `pending` row this attempt_id still owns, on its own failure path.

        A no-op if the row is already gone or no longer `pending` under this
        attempt_id (someone else - reclaim - is already handling it).
        """
        ...

    def renew(
        self,
        tx: WriteTransaction,
        group_key: str,
        attempt_id: str,
        *,
        ttl_seconds: int,
        now: str | None = None,
    ) -> None:
        """Extend an unexpired pending lease owned by this attempt.

        A fenced or expired attempt cannot renew. Raises `StateConflict` if
        the conditional update loses the race with reclaim.
        """
        ...

    def mark_committed(
        self,
        tx: WriteTransaction,
        group_key: str,
        attempt_id: str,
        *,
        keys: list[str],
    ) -> None:
        """Flip `group_key` to `committed`, in the same transaction as registration.

        Requires the row to still be `pending` under this exact attempt_id
        *and* requires `keys` to match exactly what was recorded at `acquire`
        time. Both conditions are checked, not assumed: this is what stops a
        newer attempt from registering an older attempt's key once the older
        one has gone leaseless. Raises `StateConflict` otherwise, so the
        caller's transaction rolls back rather than registering anything.
        """
        ...

    def live_physical_keys(self, tx: ReadTransaction) -> set[str]:
        """Keys covered by an unexpired `pending` or any `reclaiming` row.

        Used to exclude an active writer's key from `inspect_orphans`
        candidacy. A `committed` row's keys are not included - they are
        already excluded by the ordinary database-reference check.
        """
        ...

    def expired_pending(self, tx: ReadTransaction, now: str) -> list[dict]:
        """`pending` rows whose `lease_expires_at` has passed.

        Each entry: `group_key`, `attempt_id`, `keys`.
        """
        ...

    def fence(
        self,
        tx: WriteTransaction,
        group_key: str,
        attempt_id: str,
        *,
        now: str,
        reclaim_deadline: str,
    ) -> bool:
        """Conditionally move `pending` -> `reclaiming`, stamping a reclaim deadline.

        Conditioned on the same (`group_key`, `attempt_id`, state='pending')
        a genuine registration's `mark_committed` also requires, so the two
        serialize against each other at the database row level. Returns
        whether this call won the transition.
        """
        ...

    def stale_reclaiming(self, tx: ReadTransaction, now: str) -> list[dict]:
        """`reclaiming` rows whose `reclaim_deadline_at` has passed.

        A prior `reclaim_orphans` call fenced these and then stopped before
        finishing. Each entry: `group_key`, `attempt_id`, `keys`.
        """
        ...

    def delete_row(self, tx: WriteTransaction, group_key: str, attempt_id: str) -> None:
        """Remove a `reclaiming` row this attempt_id still owns. Idempotent."""
        ...
