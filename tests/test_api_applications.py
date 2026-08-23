"""M3 Stage B: Application commands first, then their HTTP mappings."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from cv_engine.api.app import API_PREFIX, DEFAULT_PORT, create_app
from cv_engine.application.commands import (
    CloseApplicationCommand,
    CreateJobSnapshotCommand,
    DuplicateCheckCommand,
    IngestCommand,
)
from cv_engine.application.errors import (
    DuplicateAcknowledgementRequired,
    StateConflict,
)
from cv_engine.runtime.composition import build_api_services

ALLOWED_ORIGIN = f"http://127.0.0.1:{DEFAULT_PORT}"
MUTATION_HEADERS = {"Origin": ALLOWED_ORIGIN}


def test_duplicate_check_reports_each_matching_contract(services) -> None:
    url_match = services.applications.ingest(
        IngestCommand(
            company="URL Co",
            target_role="URL Role",
            job_text="Unique URL source text",
            source_url="https://jobs.example/url-role",
        )
    )
    text_match = services.applications.ingest(
        IngestCommand(
            company="Text Co",
            target_role="Text Role",
            job_text="Second unique job text",
            source_url="https://jobs.example/text-role",
        )
    )
    heuristic_match = services.applications.ingest(
        IngestCommand(
            company="Heuristic Co",
            target_role="Platform Engineer",
            job_text="Third unique job text",
            source_url="https://jobs.example/heuristic-role",
        )
    )

    result = services.applications.duplicate_check(
        DuplicateCheckCommand(
            company="  HEURISTIC   co ",
            target_role="platform engineer",
            job_text="SECOND  unique\njob text",
            source_url="https://jobs.example/url-role",
        )
    )

    matches = {match.application_id: match.matched_on for match in result.matches}
    assert matches == {
        url_match.application_id: ["source_url"],
        text_match.application_id: ["normalized_text"],
        heuristic_match.application_id: ["company_title"],
    }


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
    snapshots = services.workspace.artifacts_root / "snapshots"
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


def test_repeating_exact_snapshot_content_is_refused_before_a_payload_write(services) -> None:
    created = services.applications.ingest(
        IngestCommand(company="Repeat Co", target_role="Developer", job_text="Exact text")
    )
    snapshots = services.workspace.artifacts_root / "snapshots" / created.application_id
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


def test_close_application_appends_policy_and_audit_records_without_touching_snapshot(
    services,
) -> None:
    created = services.applications.ingest(
        IngestCommand(company="Close Co", target_role="Developer", job_text="Closing role")
    )
    snapshot_before = services.repository.get_snapshot(created.job_snapshot_id)

    result = services.tracking.close_application(
        CloseApplicationCommand(application_id=created.application_id, client="web")
    )

    assert result.current_status == "closed"
    assert result.event_id is not None
    assert services.repository.get_snapshot(created.job_snapshot_id) == snapshot_before
    events = services.repository.recruitment_events(created.application_id)
    assert [event["to_status"] for event in events] == ["saved", "closed"]
    assert events[-1]["client"] == "web"
    audit = services.repository.audit_records(created.application_id)
    assert audit[-1]["action"] == "transition_recruitment_status"


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


def test_application_http_enforces_url_length_and_control_character_limits(services) -> None:
    base = {
        "company": "URL Safety Co",
        "target_role": "Developer",
        "job_text": "A safe posting",
    }
    with TestClient(create_app(build_api_services(services))) as api:
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


def test_cli_ingest_requires_and_records_explicit_duplicate_acknowledgement(
    services, cli_subprocess
) -> None:
    arguments = (
        "ingest",
        "--company",
        "CLI Duplicate Co",
        "--role",
        "Developer",
        "--job-text",
        "CLI duplicate text",
        "--url",
        "https://jobs.example/cli-duplicate",
    )
    first = cli_subprocess(*arguments)
    assert first.returncode == 0, first.stderr

    refused = cli_subprocess(*arguments)
    assert refused.returncode == 2
    assert "require explicit acknowledgement" in refused.stderr

    accepted = cli_subprocess(*arguments, "--acknowledge-duplicates")
    assert accepted.returncode == 0, accepted.stderr
    body = json.loads(accepted.stdout)
    assert body["warnings"] == [
        "DUPLICATE_SOURCE_URL",
        "DUPLICATE_NORMALIZED_TEXT",
        "DUPLICATE_COMPANY_TITLE",
    ]
    events = services.repository.recruitment_events(body["application_id"])
    assert events[0]["actor_type"] == "user"
    assert events[0]["client"] == "cli"
