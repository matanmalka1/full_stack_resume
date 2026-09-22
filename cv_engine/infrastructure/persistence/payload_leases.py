"""SQL adapter for `payload_write_leases` (architecture.md §7.1).

Every conditional statement here matches on `group_key` (the primary key)
together with `attempt_id` and, for `acquire`/`mark_committed`, `state`. That
match is what serializes a genuine registration against a concurrent
`reclaim_orphans` fencing pass on the same row: whichever transaction's
conditional update lands first wins it, and the other affects zero rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from ...application.errors import StateConflict
from ...util import utc_now
from .connection import SqlAlchemyTransactionManager
from .tables import payload_write_leases


def _expiry(now: str, ttl_seconds: int) -> str:
    if ttl_seconds < 1:
        raise ValueError("ttl_seconds must be positive")
    return (datetime.fromisoformat(now) + timedelta(seconds=ttl_seconds)).isoformat()


def _row_to_entry(row: Any) -> dict:
    return {
        "group_key": row["group_key"],
        "attempt_id": row["attempt_id"],
        "keys": list(row["keys_json"]),
    }


def _expected_keys(group_key: str, attempt_id: str) -> list[str]:
    """Derive allowed physical references from the claimed write identity."""
    if group_key.startswith("revision:"):
        _, application_id, revision_id = group_key.split(":")
        stem = f"artifacts/revisions/{application_id}/{revision_id}/{attempt_id}"
        return sorted((f"{stem}/resume.json", f"{stem}/resume.md"))
    if group_key.startswith("render:"):
        _, application_id, revision_id, html_id, pdf_id = group_key.split(":")
        if attempt_id != f"{html_id}:{pdf_id}":
            raise StateConflict("render lease attempt does not match its artifact IDs")
        stem = f"artifacts/outputs/{application_id}/{revision_id}"
        return sorted((f"{stem}/{html_id}.html", f"{stem}/{pdf_id}.pdf"))
    if group_key != attempt_id:
        raise StateConflict("single-payload lease attempt does not match its key")
    return [group_key]


class SqlAlchemyPayloadLeaseStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def acquire(
        self,
        tx,
        group_key: str,
        attempt_id: str,
        *,
        keys: list[str],
        ttl_seconds: int,
        now: str | None = None,
    ) -> None:
        timestamp = now or utc_now()
        if sorted(keys) != _expected_keys(group_key, attempt_id):
            raise StateConflict("payload write lease keys do not belong to this attempt")
        connection = self._transactions.connection_for(tx, access="write")
        try:
            connection.execute(
                insert(payload_write_leases).values(
                    group_key=group_key,
                    attempt_id=attempt_id,
                    state="pending",
                    owner=attempt_id,
                    keys_json=sorted(keys),
                    claimed_at=timestamp,
                    lease_expires_at=_expiry(timestamp, ttl_seconds),
                )
            )
        except IntegrityError as exc:
            raise StateConflict(
                f"payload write lease already held for {group_key}"
            ) from exc

    def release(self, tx, group_key: str, attempt_id: str) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        connection.execute(
            delete(payload_write_leases).where(
                payload_write_leases.c.group_key == group_key,
                payload_write_leases.c.attempt_id == attempt_id,
                payload_write_leases.c.state == "pending",
            )
        )

    def renew(
        self,
        tx,
        group_key: str,
        attempt_id: str,
        *,
        ttl_seconds: int,
        now: str | None = None,
    ) -> None:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(payload_write_leases)
            .where(
                payload_write_leases.c.group_key == group_key,
                payload_write_leases.c.attempt_id == attempt_id,
                payload_write_leases.c.state == "pending",
                payload_write_leases.c.lease_expires_at > timestamp,
            )
            .values(lease_expires_at=_expiry(timestamp, ttl_seconds))
        ).rowcount
        if changed != 1:
            raise StateConflict(f"payload write lease for {group_key} cannot be renewed")

    def mark_committed(
        self,
        tx,
        group_key: str,
        attempt_id: str,
        *,
        keys: list[str],
    ) -> None:
        if sorted(keys) != _expected_keys(group_key, attempt_id):
            raise StateConflict("payload registration keys do not belong to this attempt")
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(payload_write_leases)
            .where(
                payload_write_leases.c.group_key == group_key,
                payload_write_leases.c.attempt_id == attempt_id,
                payload_write_leases.c.state == "pending",
                payload_write_leases.c.keys_json == sorted(keys),
                payload_write_leases.c.lease_expires_at > utc_now(),
            )
            .values(state="committed", committed_at=utc_now())
        ).rowcount
        if changed != 1:
            raise StateConflict(
                f"payload write lease for {group_key} is not held by attempt "
                f"{attempt_id} with the keys being registered"
            )

    def live_physical_keys(self, tx) -> set[str]:
        connection = self._transactions.connection_for(tx)
        rows = connection.execute(
            select(payload_write_leases.c.keys_json).where(
                or_(
                    payload_write_leases.c.state == "reclaiming",
                    and_(
                        payload_write_leases.c.state == "pending",
                        payload_write_leases.c.lease_expires_at > utc_now(),
                    ),
                )
            )
        ).scalars()
        result: set[str] = set()
        for keys in rows:
            result.update(keys)
        return result

    def expired_pending(self, tx, now: str) -> list[dict]:
        connection = self._transactions.connection_for(tx)
        rows = (
            connection.execute(
                select(payload_write_leases).where(
                    payload_write_leases.c.state == "pending",
                    payload_write_leases.c.lease_expires_at <= now,
                )
            )
            .mappings()
            .all()
        )
        return [_row_to_entry(row) for row in rows]

    def fence(
        self,
        tx,
        group_key: str,
        attempt_id: str,
        *,
        now: str,
        reclaim_deadline: str,
    ) -> bool:
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(payload_write_leases)
            .where(
                payload_write_leases.c.group_key == group_key,
                payload_write_leases.c.attempt_id == attempt_id,
                payload_write_leases.c.state == "pending",
                payload_write_leases.c.lease_expires_at <= now,
            )
            .values(state="reclaiming", reclaim_deadline_at=reclaim_deadline)
        ).rowcount
        return changed == 1

    def stale_reclaiming(self, tx, now: str) -> list[dict]:
        connection = self._transactions.connection_for(tx)
        rows = (
            connection.execute(
                select(payload_write_leases).where(
                    payload_write_leases.c.state == "reclaiming",
                    payload_write_leases.c.reclaim_deadline_at <= now,
                )
            )
            .mappings()
            .all()
        )
        return [_row_to_entry(row) for row in rows]

    def delete_row(self, tx, group_key: str, attempt_id: str) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        connection.execute(
            delete(payload_write_leases).where(
                payload_write_leases.c.group_key == group_key,
                payload_write_leases.c.attempt_id == attempt_id,
                payload_write_leases.c.state == "reclaiming",
            )
        )
