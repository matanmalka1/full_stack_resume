"""Orphan reclaim removes only old, unregistered payloads (architecture.md §7.1)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from cv_engine.application.commands import IngestCommand
from cv_engine.application.errors import InfrastructureFailure
from cv_engine.application.maintenance import ORPHAN_MIN_AGE


def _age(path, *, by=ORPHAN_MIN_AGE * 2) -> None:
    stamp = (datetime.now(UTC) - by).timestamp()
    os.utime(path, (stamp, stamp))


def _store(services, application_id: str, snapshot_id: str, *, old: bool) -> str:
    stored = services.payloads.commit(
        services.payloads.snapshot_path(application_id, snapshot_id),
        payload=b"job text",
        validate=lambda _payload: True,
    )
    if old:
        _age(stored.path)
    return stored.project_relative


def test_reclaim_removes_old_unregistered_payloads_only(services) -> None:
    """A fresh write may still be on its way to registration; a registered one is evidence."""
    services.applications.ingest(
        IngestCommand(company="Kept Co", target_role="Developer", job_text="Python", client="web")
    )
    registered = services.payloads.payload_inventory()
    assert len(registered) == 1
    _age(services.paths.root / registered[0])
    orphan = _store(services, "abandoned", "snapshot", old=True)
    fresh = _store(services, "in-flight", "snapshot", old=False)

    assert services.maintenance.inspect_orphans().candidates == [orphan]
    assert services.maintenance.reclaim_orphans().removed == [orphan]
    assert set(services.payloads.payload_inventory()) == {registered[0], fresh}
    assert services.maintenance.reclaim_orphans().removed == []


def test_reclaim_refuses_a_candidate_that_became_registered(services, monkeypatch) -> None:
    """The reference check runs again immediately before deleting."""
    key = _store(services, "app", "snapshot", old=True)
    reads = iter([set(), {key}])
    monkeypatch.setattr(
        services.maintenance.inspection,
        "registered_payload_references",
        lambda _tx: next(reads),
    )

    with pytest.raises(InfrastructureFailure, match="integrity failure"):
        services.maintenance.reclaim_orphans()
    assert key in services.payloads.payload_inventory()
