"""Orphan inspection reports old, unregistered payloads and deletes nothing.

No path in the system deletes an immutable payload (architecture.md §7.1), so
inspection is the whole of orphan handling.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from cv_engine.application.maintenance import ORPHAN_MIN_AGE
from cv_engine.infrastructure.object_store import LocalObjectStore, S3ObjectStore
from cv_engine.infrastructure.payloads import PayloadStore


def _age(path) -> None:
    stamp = (datetime.now(UTC) - ORPHAN_MIN_AGE * 2).timestamp()
    os.utime(path, (stamp, stamp))


def _store(services, application_id: str, *, old: bool) -> str:
    destination = services.payloads.submission_path(application_id, "submission", suffix=".pdf")
    stored = services.payloads.commit(
        destination, payload=b"%PDF-1.4", validate=lambda _payload: True
    )
    if old:
        _age(destination)
    return stored.project_relative


def test_inspection_lists_old_unregistered_payloads_and_deletes_nothing(
    submitted_application,
) -> None:
    """A fresh write may still be on its way to registration; a registered one is evidence."""
    services, _application_id = submitted_application("Kept Co")
    registered = services.payloads.payload_inventory()
    assert len(registered) == 2  # the Submission's HTML and PDF copies
    for reference in registered:
        _age(services.paths.root / reference)
    orphan = _store(services, "abandoned", old=True)
    fresh = _store(services, "in-flight", old=False)

    assert services.maintenance.inspect_orphans().candidates == [orphan]
    assert set(services.payloads.payload_inventory()) == {*registered, orphan, fresh}


def test_no_store_can_delete_an_immutable_payload() -> None:
    """Immutability is structural: neither the payload store nor a backend offers deletion."""
    for store in (PayloadStore, LocalObjectStore, S3ObjectStore):
        assert not any(name.startswith("delete") for name in vars(store)), store.__name__
