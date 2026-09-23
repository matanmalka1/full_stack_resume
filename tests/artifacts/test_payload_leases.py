"""The database boundary that keeps orphan reclaim from deleting registered evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cv_engine.application.errors import InfrastructureFailure, StateConflict
from cv_engine.infrastructure.persistence.tables import payload_write_leases


@pytest.fixture
def lease_transactions(services):
    """Use the manager that owns the composed lease adapter tokens."""
    return services.maintenance.transactions


def _past(seconds: int = 600) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


def _lease_row(transactions, group_key: str):
    with transactions.read() as tx:
        connection = transactions.connection_for(tx)
        return (
            connection.execute(
                payload_write_leases.select().where(payload_write_leases.c.group_key == group_key)
            )
            .mappings()
            .one_or_none()
        )


def test_lease_registration_requires_matching_attempt_and_keys(
    services, lease_transactions
) -> None:
    leases = services.maintenance.leases
    first = "artifacts/snapshots/app/first.txt"
    second = "artifacts/snapshots/app/second.txt"
    with lease_transactions.write() as tx:
        leases.acquire(tx, first, first, keys=[first], ttl_seconds=300)
    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, first, first, keys=[second])
    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, first, second, keys=[first])
    with lease_transactions.write() as tx:
        leases.mark_committed(tx, first, first, keys=[first])
    assert _lease_row(lease_transactions, first)["state"] == "committed"


def test_only_fencing_is_authoritative_over_a_lease(services, lease_transactions) -> None:
    """Expiry alone is never authoritative - only fencing is (architecture.md §7.1).

    A write slower than its nominal TTL, but never actually reclaimed, must
    still be able to register: the alternative reintroduces "TTL proves
    abandonment", which the design explicitly rejects. A fenced lease cannot
    register, and a renewed lease cannot be fenced from an old expiry snapshot.
    """
    leases = services.maintenance.leases
    slow = "artifacts/snapshots/app/slow.txt"
    with lease_transactions.write() as tx:
        leases.acquire(tx, slow, slow, keys=[slow], ttl_seconds=1, now=_past())
    with lease_transactions.write() as tx:
        leases.mark_committed(tx, slow, slow, keys=[slow])
    assert _lease_row(lease_transactions, slow)["state"] == "committed"

    fenced = "artifacts/snapshots/app/fenced.txt"
    with lease_transactions.write() as tx:
        leases.acquire(tx, fenced, fenced, keys=[fenced], ttl_seconds=1, now=_past())
    with lease_transactions.write() as tx:
        assert leases.fence(tx, fenced, fenced, now=_past(500), reclaim_deadline=_past())
    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, fenced, fenced, keys=[fenced])

    renewed = "artifacts/snapshots/app/snapshot.txt"
    with lease_transactions.write() as tx:
        leases.acquire(tx, renewed, renewed, keys=[renewed], ttl_seconds=20, now=_past(10))
    with lease_transactions.write() as tx:
        leases.renew(tx, renewed, renewed, ttl_seconds=300, now=_past(5))
    with lease_transactions.write() as tx:
        assert not leases.fence(tx, renewed, renewed, now=_past(5), reclaim_deadline=_past(1))
    assert _lease_row(lease_transactions, renewed)["state"] == "pending"


def test_revision_group_commit_rolls_back_as_one_transaction(services, lease_transactions) -> None:
    leases = services.maintenance.leases
    group = "revision:app:revision"
    keys = [
        services.payloads.reference_for(
            services.payloads.revision_path("app", "revision", "attempt", format=fmt)
        )
        for fmt in ("json", "md")
    ]
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, "attempt", keys=keys, ttl_seconds=300)

    with pytest.raises(RuntimeError, match="registration failed"):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, group, "attempt", keys=keys)
            raise RuntimeError("registration failed")
    assert _lease_row(lease_transactions, group)["state"] == "pending"

    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, group, "attempt", keys=keys[:1])
    with lease_transactions.write() as tx:
        leases.mark_committed(tx, group, "attempt", keys=keys)
    assert _lease_row(lease_transactions, group)["state"] == "committed"


def test_revision_retry_cannot_claim_or_register_a_prior_attempts_keys(
    services, lease_transactions
) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    group = "revision:app:revision"

    def keys_for(attempt: str) -> list[str]:
        return [
            payloads.reference_for(payloads.revision_path("app", "revision", attempt, format=fmt))
            for fmt in ("json", "md")
        ]

    old_keys = keys_for("old")
    new_keys = keys_for("new")
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, "old", keys=old_keys, ttl_seconds=300)
    with lease_transactions.write() as tx:
        leases.release(tx, group, "old")
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, "new", keys=new_keys, ttl_seconds=300)
    # "new" can only register what it actually claimed at acquire time - not
    # "old"'s keys, even though both attempts share the same group_key.
    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, group, "new", keys=old_keys)
    assert _lease_row(lease_transactions, group)["state"] == "pending"


def test_render_group_binds_both_artifact_keys(services, lease_transactions) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    attempt = "html-id:pdf-id"
    group = f"render:app:revision:{attempt}"
    keys = [
        payloads.reference_for(payloads.output_path("app", "revision", "html-id", suffix="html")),
        payloads.reference_for(payloads.output_path("app", "revision", "pdf-id", suffix="pdf")),
    ]
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, attempt, keys=keys, ttl_seconds=300)
    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.mark_committed(tx, group, attempt, keys=[keys[0], keys[0]])
    with lease_transactions.write() as tx:
        leases.mark_committed(tx, group, attempt, keys=keys)
    assert _lease_row(lease_transactions, group)["state"] == "committed"


def test_reclaim_removes_only_abandoned_unreferenced_payloads(services, lease_transactions) -> None:
    """Each scenario uses its own application, so one sweep cannot answer for another.

    A retry reclaims only its own expired revision group and then claims it
    afresh. A sweep removes an expired group's payload, and a late leaseless
    write from the fenced writer is removed by the next sweep. An unexpired
    writer is hidden from inspection and left alone. A stale reclaiming row
    cannot be renewed and is resumed.
    """
    leases = services.maintenance.leases
    payloads = services.payloads

    def revision_keys(app: str, attempt: str) -> list[str]:
        return [
            payloads.reference_for(payloads.revision_path(app, "revision", attempt, format=fmt))
            for fmt in ("json", "md")
        ]

    group = "revision:retry:revision"
    old_path = payloads.revision_path("retry", "revision", "old", format="json")
    old_keys = revision_keys("retry", "old")
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, "old", keys=old_keys, ttl_seconds=1, now=_past())
    payloads.commit(old_path, payload=b"{}", validate=lambda _: True)

    assert old_keys[0] in services.maintenance.reclaim_group(group).removed
    assert not old_path.exists()
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, "new", keys=revision_keys("retry", "new"), ttl_seconds=300)
    assert _lease_row(lease_transactions, group)["attempt_id"] == "new"

    writer_path = payloads.snapshot_path("writer", "snapshot")
    writer_key = payloads.reference_for(writer_path)
    with lease_transactions.write() as tx:
        leases.acquire(tx, writer_key, writer_key, keys=[writer_key], ttl_seconds=300)
    payloads.commit(writer_path, payload=b"still writing", validate=lambda _: True)

    group = "revision:sweep:revision"
    paths = [
        payloads.revision_path("sweep", "revision", "attempt", format=fmt) for fmt in ("json", "md")
    ]
    keys = [payloads.reference_for(path) for path in paths]
    with lease_transactions.write() as tx:
        leases.acquire(tx, group, "attempt", keys=keys, ttl_seconds=1, now=_past())
    payloads.commit(paths[0], payload=b"{}", validate=lambda _: True)
    candidates = services.maintenance.inspect_orphans().candidates
    assert keys[0] in candidates
    assert writer_key not in candidates

    reclaimed = services.maintenance.reclaim_orphans()
    assert keys[0] in reclaimed.removed
    assert writer_key not in reclaimed.removed
    assert not paths[0].exists()
    assert writer_path.exists()
    assert _lease_row(lease_transactions, group) is None

    # The old writer can still finish a storage put after fencing. Its lease
    # cannot be recovered, so a later sweep must remove that new orphan.
    payloads.commit(paths[1], payload=b"late", validate=lambda _: True)
    assert keys[1] in services.maintenance.reclaim_orphans().removed
    assert not paths[1].exists()

    stale_path = payloads.snapshot_path("stale", "snapshot")
    stale_key = payloads.reference_for(stale_path)
    with lease_transactions.write() as tx:
        leases.acquire(tx, stale_key, stale_key, keys=[stale_key], ttl_seconds=1, now=_past())
    payloads.commit(stale_path, payload=b"snapshot", validate=lambda _: True)
    with lease_transactions.write() as tx:
        assert leases.fence(tx, stale_key, stale_key, now=_past(1), reclaim_deadline=_past(1))
    with pytest.raises(StateConflict):
        with lease_transactions.write() as tx:
            leases.renew(tx, stale_key, stale_key, ttl_seconds=300)

    assert stale_key in services.maintenance.reclaim_orphans().removed
    assert not stale_path.exists()
    assert _lease_row(lease_transactions, stale_key) is None
    assert writer_path.exists()


def test_reclaim_refuses_to_delete_a_referenced_payload(
    services, lease_transactions, monkeypatch
) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    path = payloads.snapshot_path("app", "snapshot")
    key = payloads.reference_for(path)
    with lease_transactions.write() as tx:
        leases.acquire(tx, key, key, keys=[key], ttl_seconds=1, now=_past())
    payloads.commit(path, payload=b"evidence", validate=lambda _: True)
    monkeypatch.setattr(
        services.maintenance.inspection,
        "registered_payload_references",
        lambda _tx: {key},
    )

    with pytest.raises(InfrastructureFailure, match="database still references"):
        services.maintenance.reclaim_orphans()
    assert path.read_bytes() == b"evidence"
