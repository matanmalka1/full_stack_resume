"""M3 Stage B: Application commands first, then their HTTP mappings."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cv_engine.api.app import API_PREFIX, DEFAULT_PORT, create_app
from cv_engine.application.commands import (
    CreateJobSnapshotCommand,
    IngestCommand,
)
from cv_engine.application.errors import (
    DuplicateAcknowledgementRequired,
    InfrastructureFailure,
    StateConflict,
)
from cv_engine.infrastructure.persistence.audit import SqlAlchemyAuditRepository
from cv_engine.runtime.composition import build_api_services

ALLOWED_ORIGIN = f"http://127.0.0.1:{DEFAULT_PORT}"
MUTATION_HEADERS = {"Origin": ALLOWED_ORIGIN}


def test_duplicate_acknowledgement_precedes_every_write_and_retry_keeps_warnings(
    services,
) -> None:
    original = services.applications.ingest(
        IngestCommand(
            company="Duplicate Co",
            target_role="Developer",
            job_text="A duplicate-sensitive role",
            source_url="https://jobs.example/duplicate",
        )
    )
    snapshots = services.paths.artifacts_root / "snapshots"
    files_before = sorted(snapshots.rglob("*.txt"))
    applications_before = services.repository.list_applications()
    command = IngestCommand(
        company=" duplicate  co ",
        target_role="DEVELOPER",
        job_text="A  duplicate-sensitive\nrole",
        source_url="https://jobs.example/duplicate",
        client="web",
    )

    try:
        services.applications.ingest(command)
    except DuplicateAcknowledgementRequired as error:
        assert error.code == "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED"
        assert error.matches == [
            {
                "application_id": original.application_id,
                "company": "Duplicate Co",
                "target_role": "Developer",
                "matched_on": ["source_url", "normalized_text", "company_title"],
            }
        ]
    else:
        raise AssertionError("unacknowledged duplicates must be refused")

    assert services.repository.list_applications() == applications_before
    assert sorted(snapshots.rglob("*.txt")) == files_before

    created = services.applications.ingest(
        command.model_copy(update={"acknowledged_duplicates": True})
    )
    assert created.warnings == [
        "DUPLICATE_SOURCE_URL",
        "DUPLICATE_NORMALIZED_TEXT",
        "DUPLICATE_COMPANY_TITLE",
    ]
    assert created.duplicate_matches[0].application_id == original.application_id
    creation_event = services.repository.recruitment_events(created.application_id)[0]
    assert creation_event["actor_type"] == "user"
    assert creation_event["client"] == "web"


def test_create_job_snapshot_preserves_exact_historical_payload_and_lineage(services) -> None:
    initial_text = "Initial line\n"
    created = services.applications.ingest(
        IngestCommand(company="Snapshot Co", target_role="Developer", job_text=initial_text)
    )
    initial = services.repository.get_snapshot(created.job_snapshot_id)
    replacement_text = "Replacement line one\r\nReplacement line two\n"

    replacement = services.applications.create_job_snapshot(
        CreateJobSnapshotCommand(
            application_id=created.application_id,
            job_text=replacement_text,
            source_url="https://jobs.example/replacement",
            source_metadata={"source_label": "updated posting"},
            actor_type="system",
            client="worker",
        )
    )

    historical = services.repository.get_snapshot(created.job_snapshot_id)
    latest = services.repository.get_snapshot(replacement.job_snapshot_id)
    assert historical == initial
    assert (
        services.payloads.read_snapshot(historical["payload_path"], historical["source_hash"])
        == initial_text
    )
    assert services.payloads.read_snapshot(latest["payload_path"], latest["source_hash"]) == (
        replacement_text
    )
    assert latest["prior_snapshot_id"] == created.job_snapshot_id
    assert latest["version_number"] == 2
    detail = services.queries.application_detail(created.application_id)
    assert detail.latest_snapshot.id == replacement.job_snapshot_id
    assert detail.latest_snapshot.job_text == replacement_text
    audit = services.repository.audit_records(created.application_id)
    assert len(audit) == 1
    assert audit[0]["action"] == "create_job_snapshot"
    assert audit[0]["entity_type"] == "job_snapshot"
    assert audit[0]["entity_id"] == replacement.job_snapshot_id
    assert audit[0]["actor_type"] == "system"
    assert audit[0]["client"] == "worker"
    assert audit[0]["occurred_at"] == latest["captured_at"]


def test_job_snapshot_metadata_rolls_back_when_its_audit_insert_fails(
    services, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = services.applications.ingest(
        IngestCommand(company="Audit Rollback Co", target_role="Developer", job_text="Initial")
    )
    snapshots = services.paths.artifacts_root / "snapshots" / created.application_id
    files_before = sorted(snapshots.iterdir())

    def refuse_audit(_repository, _record) -> None:
        raise InfrastructureFailure("injected audit failure")

    monkeypatch.setattr(SqlAlchemyAuditRepository, "insert_audit", refuse_audit)
    with pytest.raises(InfrastructureFailure, match="injected audit failure"):
        services.applications.create_job_snapshot(
            CreateJobSnapshotCommand(
                application_id=created.application_id,
                job_text="Replacement",
            )
        )

    assert services.repository.latest_snapshot(created.application_id)["version_number"] == 1
    assert services.repository.audit_records(created.application_id) == []
    assert len(list(snapshots.iterdir())) == len(files_before) + 1


def test_repeating_exact_snapshot_content_is_refused_before_a_payload_write(services) -> None:
    created = services.applications.ingest(
        IngestCommand(company="Repeat Co", target_role="Developer", job_text="Exact text")
    )
    snapshots = services.paths.artifacts_root / "snapshots" / created.application_id
    files_before = sorted(snapshots.iterdir())

    try:
        services.applications.create_job_snapshot(
            CreateJobSnapshotCommand(
                application_id=created.application_id,
                job_text="Exact text",
            )
        )
    except StateConflict as error:
        assert "already has a snapshot" in str(error)
    else:
        raise AssertionError("the immutable per-application content identity must be preserved")

    assert sorted(snapshots.iterdir()) == files_before
    assert services.repository.latest_snapshot(created.application_id)["version_number"] == 1


def test_application_http_create_read_snapshot_and_close_sequence(services) -> None:
    with TestClient(create_app(build_api_services(services))) as api:
        created = api.post(
            f"{API_PREFIX}/applications",
            headers=MUTATION_HEADERS,
            json={
                "company": "HTTP Co",
                "target_role": "Developer",
                "job_text": "HTTP initial text\r\n",
                "source_url": "https://jobs.example/http",
            },
        )
        assert created.status_code == 201
        application_id = created.json()["application_id"]
        snapshot_id = created.json()["job_snapshot_id"]

        listed = api.get(f"{API_PREFIX}/applications")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["items"]] == [application_id]

        detail = api.get(f"{API_PREFIX}/applications/{application_id}")
        assert detail.status_code == 200
        assert detail.json()["latest_snapshot"]["id"] == snapshot_id
        assert detail.json()["latest_snapshot"]["job_text"] == "HTTP initial text\r\n"

        replacement = api.post(
            f"{API_PREFIX}/applications/{application_id}/job-snapshots",
            headers=MUTATION_HEADERS,
            json={
                "job_text": "HTTP replacement text\n",
                "source_metadata": {"source_label": "revision"},
            },
        )
        assert replacement.status_code == 201
        replacement_id = replacement.json()["job_snapshot_id"]
        snapshot_audit = services.repository.audit_records(application_id)
        assert snapshot_audit[-1]["action"] == "create_job_snapshot"
        assert snapshot_audit[-1]["actor_type"] == "user"
        assert snapshot_audit[-1]["client"] == "web"

        closed = api.post(
            f"{API_PREFIX}/applications/{application_id}/close",
            headers=MUTATION_HEADERS,
        )
        assert closed.status_code == 200
        assert closed.json()["current_status"] == "closed"

        final = api.get(f"{API_PREFIX}/applications/{application_id}")
        assert final.status_code == 200
        assert final.json()["latest_snapshot"]["id"] == replacement_id
        assert final.json()["latest_snapshot"]["prior_snapshot_id"] == snapshot_id
        assert final.json()["recruitment_status"] == "closed"


def test_application_http_duplicate_precheck_and_acknowledgement_contract(services) -> None:
    payload = {
        "company": "HTTP Duplicate Co",
        "target_role": "Developer",
        "job_text": "Duplicate HTTP text",
        "source_url": "https://jobs.example/http-duplicate",
    }
    with TestClient(create_app(build_api_services(services))) as api:
        original = api.post(
            f"{API_PREFIX}/applications",
            headers=MUTATION_HEADERS,
            json=payload,
        )
        assert original.status_code == 201

        checked = api.post(
            f"{API_PREFIX}/applications/duplicate-check",
            headers=MUTATION_HEADERS,
            json=payload,
        )
        assert checked.status_code == 200
        assert checked.json()["matches"][0]["matched_on"] == [
            "source_url",
            "normalized_text",
            "company_title",
        ]

        refused = api.post(
            f"{API_PREFIX}/applications",
            headers=MUTATION_HEADERS,
            json=payload,
        )
        assert refused.status_code == 412
        assert refused.json()["code"] == "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED"
        assert refused.json()["context"]["matches"] == checked.json()["matches"]
        assert len(api.get(f"{API_PREFIX}/applications").json()["items"]) == 1

        accepted = api.post(
            f"{API_PREFIX}/applications",
            headers=MUTATION_HEADERS,
            json={**payload, "acknowledged_duplicates": True},
        )
        assert accepted.status_code == 201
        assert accepted.json()["warnings"] == [
            "DUPLICATE_SOURCE_URL",
            "DUPLICATE_NORMALIZED_TEXT",
            "DUPLICATE_COMPANY_TITLE",
        ]
        assert len(api.get(f"{API_PREFIX}/applications").json()["items"]) == 2
        base = {
            "company": "URL Safety Co",
            "target_role": "Developer",
            "job_text": "A safe posting",
        }
        controlled = api.post(
            f"{API_PREFIX}/applications/duplicate-check",
            headers=MUTATION_HEADERS,
            json={**base, "source_url": "https://jobs.example/unsafe\u0000"},
        )
        too_long = api.post(
            f"{API_PREFIX}/applications/duplicate-check",
            headers=MUTATION_HEADERS,
            json={**base, "source_url": "https://jobs.example/" + "x" * 2048},
        )

        assert controlled.status_code == 412
        assert controlled.json()["code"] == "PRECONDITION_FAILED"
        assert too_long.status_code == 422
