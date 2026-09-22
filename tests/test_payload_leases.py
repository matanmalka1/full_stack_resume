"""The database boundary that keeps orphan reclaim from deleting registered evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cv_engine.application.errors import InfrastructureFailure, StateConflict
from cv_engine.infrastructure.persistence.tables import payload_write_leases


def _past(seconds: int = 600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _lease_row(transactions, group_key: str):
    with transactions.read() as tx:
        connection = transactions.connection_for(tx)
        return connection.execute(
            payload_write_leases.select().where(payload_write_leases.c.group_key == group_key)
        ).mappings().one_or_none()


def test_lease_registration_requires_matching_attempt_keys_and_unexpired_ownership(
    services, transaction_manager
) -> None:
    leases = services.maintenance.leases
    first = "artifacts/snapshots/app/first.txt"
    second = "artifacts/snapshots/app/second.txt"
    with transaction_manager.write() as tx:
        leases.acquire(tx, first, first, keys=[first], ttl_seconds=300)
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, first, first, keys=[second])
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, first, second, keys=[first])
    with transaction_manager.write() as tx:
        leases.mark_committed(tx, first, first, keys=[first])
    assert _lease_row(transaction_manager, first)["state"] == "committed"

    with transaction_manager.write() as tx:
        leases.acquire(tx, second, second, keys=[second], ttl_seconds=1, now=_past())
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, second, second, keys=[second])


def test_renewed_lease_cannot_be_fenced_from_an_old_expiry_snapshot(
    services, transaction_manager
) -> None:
    leases = services.maintenance.leases
    key = "artifacts/snapshots/app/snapshot.txt"
    with transaction_manager.write() as tx:
        leases.acquire(tx, key, key, keys=[key], ttl_seconds=20, now=_past(10))
    with transaction_manager.write() as tx:
        leases.renew(tx, key, key, ttl_seconds=300, now=_past(5))
    with transaction_manager.write() as tx:
        assert not leases.fence(
            tx, key, key, now=_past(5), reclaim_deadline=_past(1)
        )
    assert _lease_row(transaction_manager, key)["state"] == "pending"


def test_revision_group_commit_rolls_back_as_one_transaction(
    services, transaction_manager
) -> None:
    leases = services.maintenance.leases
    group = "revision:app:revision"
    keys = [
        services.payloads.reference_for(
            services.payloads.revision_path("app", "revision", "attempt", format=fmt)
        )
        for fmt in ("json", "md")
    ]
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, "attempt", keys=keys, ttl_seconds=300)

    with pytest.raises(RuntimeError, match="registration failed"):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, group, "attempt", keys=keys)
            raise RuntimeError("registration failed")
    assert _lease_row(transaction_manager, group)["state"] == "pending"

    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, group, "attempt", keys=keys[:1])
    with transaction_manager.write() as tx:
        leases.mark_committed(tx, group, "attempt", keys=keys)
    assert _lease_row(transaction_manager, group)["state"] == "committed"


def test_revision_retry_cannot_claim_or_register_a_prior_attempts_keys(
    services, transaction_manager
) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    group = "revision:app:revision"

    def keys_for(attempt: str) -> list[str]:
        return [
            payloads.reference_for(
                payloads.revision_path("app", "revision", attempt, format=fmt)
            )
            for fmt in ("json", "md")
        ]

    old_keys = keys_for("old")
    new_keys = keys_for("new")
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, "old", keys=old_keys, ttl_seconds=300)
    with transaction_manager.write() as tx:
        leases.release(tx, group, "old")
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.acquire(tx, group, "new", keys=old_keys, ttl_seconds=300)
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, "new", keys=new_keys, ttl_seconds=300)
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, group, "new", keys=old_keys)
    assert _lease_row(transaction_manager, group)["state"] == "pending"


def test_render_group_binds_both_artifact_keys(services, transaction_manager) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    attempt = "html-id:pdf-id"
    group = f"render:app:revision:{attempt}"
    keys = [
        payloads.reference_for(payloads.output_path("app", "revision", "html-id", suffix="html")),
        payloads.reference_for(payloads.output_path("app", "revision", "pdf-id", suffix="pdf")),
    ]
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, attempt, keys=keys, ttl_seconds=300)
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.mark_committed(tx, group, attempt, keys=[keys[0], keys[0]])
    with transaction_manager.write() as tx:
        leases.mark_committed(tx, group, attempt, keys=keys)
    assert _lease_row(transaction_manager, group)["state"] == "committed"


def test_retry_reclaims_only_its_expired_revision_group(
    services, transaction_manager
) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    group = "revision:app:revision"
    old_path = payloads.revision_path("app", "revision", "old", format="json")
    old_keys = [
        payloads.reference_for(
            payloads.revision_path("app", "revision", "old", format=fmt)
        )
        for fmt in ("json", "md")
    ]
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, "old", keys=old_keys, ttl_seconds=1, now=_past())
    payloads.commit(old_path, payload=b"{}", validate=lambda _: True)

    assert old_keys[0] in services.maintenance.reclaim_group(group).removed
    assert not old_path.exists()
    new_keys = [
        payloads.reference_for(
            payloads.revision_path("app", "revision", "new", format=fmt)
        )
        for fmt in ("json", "md")
    ]
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, "new", keys=new_keys, ttl_seconds=300)
    assert _lease_row(transaction_manager, group)["attempt_id"] == "new"


def test_reclaim_expired_revision_group_and_late_leaseless_write(
    services, transaction_manager
) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    group = "revision:app:revision"
    paths = [
        payloads.revision_path("app", "revision", "attempt", format=fmt)
        for fmt in ("json", "md")
    ]
    keys = [payloads.reference_for(path) for path in paths]
    with transaction_manager.write() as tx:
        leases.acquire(tx, group, "attempt", keys=keys, ttl_seconds=1, now=_past())
    payloads.commit(paths[0], payload=b"{}", validate=lambda _: True)
    assert keys[0] in services.maintenance.inspect_orphans().candidates

    reclaimed = services.maintenance.reclaim_orphans()
    assert keys[0] in reclaimed.removed
    assert not paths[0].exists()
    assert _lease_row(transaction_manager, group) is None

    # The old writer can still finish a storage put after fencing. Its lease
    # cannot be recovered, so a later sweep must remove that new orphan.
    payloads.commit(paths[1], payload=b"late", validate=lambda _: True)
    assert keys[1] in services.maintenance.reclaim_orphans().removed
    assert not paths[1].exists()


def test_inspection_hides_an_unexpired_writer(services, transaction_manager) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    path = payloads.snapshot_path("app", "snapshot")
    key = payloads.reference_for(path)
    with transaction_manager.write() as tx:
        leases.acquire(tx, key, key, keys=[key], ttl_seconds=300)
    payloads.commit(path, payload=b"still writing", validate=lambda _: True)

    assert key not in services.maintenance.inspect_orphans().candidates
    assert key not in services.maintenance.reclaim_orphans().removed
    assert path.exists()


def test_reclaim_resumes_stale_reclaiming_row(services, transaction_manager) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    path = payloads.snapshot_path("app", "snapshot")
    key = payloads.reference_for(path)
    with transaction_manager.write() as tx:
        leases.acquire(tx, key, key, keys=[key], ttl_seconds=1, now=_past())
    payloads.commit(path, payload=b"snapshot", validate=lambda _: True)
    with transaction_manager.write() as tx:
        assert leases.fence(tx, key, key, now=_past(1), reclaim_deadline=_past(1))
    with pytest.raises(StateConflict):
        with transaction_manager.write() as tx:
            leases.renew(tx, key, key, ttl_seconds=300)

    assert key in services.maintenance.reclaim_orphans().removed
    assert not path.exists()
    assert _lease_row(transaction_manager, key) is None


def test_reclaim_refuses_to_delete_a_referenced_payload(
    services, transaction_manager, monkeypatch
) -> None:
    leases = services.maintenance.leases
    payloads = services.payloads
    path = payloads.snapshot_path("app", "snapshot")
    key = payloads.reference_for(path)
    with transaction_manager.write() as tx:
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
