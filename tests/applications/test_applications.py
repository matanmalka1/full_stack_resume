"""M3 Stage B: Application commands first, then their HTTP mappings."""

from __future__ import annotations

import pytest

from cv_engine.api.app import API_PREFIX, DEFAULT_PORT
from cv_engine.application.commands import (
    ExternalSubmissionCommand,
    IngestCommand,
    UpdatedJobText,
    UpdateJobTextCommand,
)
from cv_engine.application.errors import (
    InfrastructureFailure,
    StateConflict,
    UnknownRecord,
)
from cv_engine.infrastructure.persistence.audit_log import SqlAlchemyAuditLog
from cv_engine.util import new_id, sha256_text, utc_now

ALLOWED_ORIGIN = f"http://127.0.0.1:{DEFAULT_PORT}"
MUTATION_HEADERS = {"Origin": ALLOWED_ORIGIN}


def test_job_text_is_exact_edited_in_place_locked_by_a_submission_and_atomic(
    services,
    monkeypatch: pytest.MonkeyPatch,
    transaction_manager,
    application_store,
    application_projection_reader,
) -> None:
    """The job text is stored exactly on the Application and edited in place.

    An edit names the text it replaces (`expected_job_text_hash`); an unchanged
    edit writes nothing; a failed audit insert rolls the edit back; a Submission
    locks the text; and a failed initial event rolls back the whole ingest.
    """
    initial_text = "עברית  English\r\n<script>x</script>\n"
    created = services.applications.ingest(
        IngestCommand(
            company="Job Text Co",
            target_role="Developer",
            job_text=initial_text,
            source_url="https://jobs.example/first",
            client="web",
        )
    )
    assert created.job_text_hash == sha256_text(initial_text)
    detail = services.queries.application_detail(created.application_id)
    assert detail.job_posting.job_text == initial_text
    assert detail.job_posting.source_url == "https://jobs.example/first"
    assert detail.job_posting.locked is False
    assert detail.job_text_hash == created.job_text_hash
    assert services.payloads.payload_inventory() == []

    replacement_text = "Replacement line one\r\nReplacement line two\n"

    def edit(text: str, expected: str, **values) -> UpdatedJobText:
        return services.applications.update_job_text(
            UpdateJobTextCommand(
                application_id=created.application_id,
                job_text=text,
                expected_job_text_hash=expected,
                **{"client": "web", **values},
            )
        )

    with pytest.raises(StateConflict, match="expected_job_text_hash"):
        edit(replacement_text, sha256_text("not what the client read"))
    replacement = edit(
        replacement_text,
        created.job_text_hash,
        source_url="https://jobs.example/second",
        actor_type="system",
        client="worker",
    )
    assert replacement.job_text_hash == sha256_text(replacement_text)
    detail = services.queries.application_detail(created.application_id)
    assert detail.job_posting.job_text == replacement_text
    assert detail.job_posting.source_url == "https://jobs.example/second"
    assert detail.job_posting.job_text_updated_at == replacement.job_text_updated_at
    with transaction_manager.read() as tx:
        audit = application_projection_reader.audit_records(tx, created.application_id)
    assert len(audit) == 1
    assert audit[0]["action"] == "update_job_text"
    assert audit[0]["entity_type"] == "application"
    assert audit[0]["actor_type"] == "system"
    assert audit[0]["client"] == "worker"
    assert audit[0]["occurred_at"] == replacement.job_text_updated_at

    def audit_count() -> int:
        with transaction_manager.read() as tx:
            return len(application_projection_reader.audit_records(tx, created.application_id))

    unchanged = edit(
        replacement_text, replacement.job_text_hash, source_url="https://jobs.example/second"
    )
    assert unchanged == replacement
    assert audit_count() == 1

    def refuse_audit(_repository, _tx, _record) -> None:
        raise InfrastructureFailure("injected audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAuditLog, "insert_audit", refuse_audit)
        with pytest.raises(InfrastructureFailure, match="injected audit failure"):
            edit("Rolled back", replacement.job_text_hash)
    assert (
        services.queries.application_detail(created.application_id).job_posting.job_text
        == replacement_text
    )
    assert audit_count() == 1

    services.submission.record_external_submission(
        ExternalSubmissionCommand(
            application_id=created.application_id, submitted_at=utc_now(), client="web"
        )
    )
    assert services.queries.application_detail(created.application_id).job_posting.locked
    with pytest.raises(StateConflict, match="locked"):
        edit("After submission", replacement.job_text_hash)
    with pytest.raises(UnknownRecord):
        services.applications.update_job_text(
            UpdateJobTextCommand(
                application_id=new_id(),
                job_text="Nobody's",
                expected_job_text_hash=replacement.job_text_hash,
                client="web",
            )
        )

    def refuse_initial_event(*args, **kwargs):
        raise RuntimeError("event refused")

    with monkeypatch.context() as patch:
        patch.setattr(
            services.applications._recruitment,
            "insert_initial_saved_event",
            refuse_initial_event,
        )
        with pytest.raises(RuntimeError, match="event refused"):
            services.applications.ingest(
                IngestCommand(
                    company="Atomic Intake",
                    target_role="Developer",
                    job_text="Python and PostgreSQL",
                    client="web",
                )
            )
    with transaction_manager.read() as tx:
        rows = application_projection_reader.applications(tx)
    assert all(row["company"] != "Atomic Intake" for row in rows)


def test_application_http_create_read_edit_and_close_sequence(
    api_paused, services, transaction_manager, application_projection_reader
) -> None:
    api = api_paused.client
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
    job_text_hash = created.json()["job_text_hash"]

    listed = api.get(f"{API_PREFIX}/applications")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [application_id]

    detail = api.get(f"{API_PREFIX}/applications/{application_id}")
    assert detail.status_code == 200
    assert detail.json()["job_text_hash"] == job_text_hash
    assert detail.json()["job_posting"]["job_text"] == "HTTP initial text\r\n"
    assert detail.json()["job_posting"]["locked"] is False

    notes = api.patch(
        f"{API_PREFIX}/applications/{application_id}/notes",
        headers=MUTATION_HEADERS,
        json={"notes": "Recruiter referred me", "expected_notes": ""},
    )
    assert notes.status_code == 200
    assert notes.json()["notes"] == "Recruiter referred me"
    stale_notes = api.patch(
        f"{API_PREFIX}/applications/{application_id}/notes",
        headers=MUTATION_HEADERS,
        json={"notes": "Overwrite", "expected_notes": ""},
    )
    assert stale_notes.status_code == 409
    assert api.get(f"{API_PREFIX}/applications/{application_id}").json()["application"][
        "notes"
    ] == ("Recruiter referred me")
    with transaction_manager.read() as tx:
        notes_audit = application_projection_reader.audit_records(tx, application_id)[-1]
    assert notes_audit["action"] == "update_application_notes"
    assert notes_audit["details_json"] == '{"field":"notes"}'

    job_text_path = f"{API_PREFIX}/applications/{application_id}/job-text"
    replacement = api.patch(
        job_text_path,
        headers=MUTATION_HEADERS,
        json={"job_text": "HTTP replacement text\n", "expected_job_text_hash": job_text_hash},
    )
    assert replacement.status_code == 200, replacement.text
    replacement_hash = replacement.json()["job_text_hash"]
    assert replacement_hash == sha256_text("HTTP replacement text\n")
    stale = api.patch(
        job_text_path,
        headers=MUTATION_HEADERS,
        json={"job_text": "Overwrite", "expected_job_text_hash": job_text_hash},
    )
    assert stale.status_code == 409
    missing = api.patch(
        f"{API_PREFIX}/applications/{new_id()}/job-text",
        headers=MUTATION_HEADERS,
        json={"job_text": "Nobody's", "expected_job_text_hash": job_text_hash},
    )
    assert missing.status_code == 404
    with transaction_manager.read() as tx:
        job_text_audit = application_projection_reader.audit_records(tx, application_id)
    assert job_text_audit[-1]["action"] == "update_job_text"
    assert job_text_audit[-1]["actor_type"] == "user"
    assert job_text_audit[-1]["client"] == "web"

    closed = api.post(
        f"{API_PREFIX}/applications/{application_id}/close",
        headers=MUTATION_HEADERS,
    )
    assert closed.status_code == 200
    assert closed.json()["current_status"] == "closed"

    final = api.get(f"{API_PREFIX}/applications/{application_id}")
    assert final.status_code == 200
    assert final.json()["job_text_hash"] == replacement_hash
    assert final.json()["job_posting"]["job_text"] == "HTTP replacement text\n"
    assert final.json()["recruitment_status"] == "closed"

    # delete_application is orthogonal to RecruitmentStatus and callable
    # from a terminal status: it neither requires nor changes `closed`.
    deleted = api.post(
        f"{API_PREFIX}/applications/{application_id}/delete",
        headers=MUTATION_HEADERS,
    )
    assert deleted.status_code == 200
    assert deleted.json()["current_status"] == "closed"

    # Excluded from the default list, but still individually reachable by ID.
    listed_after_delete = api.get(f"{API_PREFIX}/applications")
    assert application_id not in [item["id"] for item in listed_after_delete.json()["items"]]
    still_reachable = api.get(f"{API_PREFIX}/applications/{application_id}")
    assert still_reachable.status_code == 200
    assert still_reachable.json()["application"]["deleted_at"] is not None

    with transaction_manager.read() as tx:
        delete_audit = application_projection_reader.audit_records(tx, application_id)[-1]
    assert delete_audit["action"] == "delete_application"

    # Idempotency: deleting an already-deleted Application is refused (409),
    # not silently repeated - and no second `delete_application` audit event
    # is appended for it.
    redeleted = api.post(
        f"{API_PREFIX}/applications/{application_id}/delete",
        headers=MUTATION_HEADERS,
    )
    assert redeleted.status_code == 409
    with transaction_manager.read() as tx:
        assert (
            application_projection_reader.audit_records(tx, application_id)[-1]["id"]
            == delete_audit["id"]
        )

    # A duplicate application for the same posting is no longer flagged
    # against a deleted Application.
    duplicate = api.post(
        f"{API_PREFIX}/applications/duplicate-check",
        headers=MUTATION_HEADERS,
        json={
            "company": "HTTP Co",
            "target_role": "Developer",
            "job_text": "HTTP replacement text\n",
            "source_url": "https://jobs.example/http",
        },
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["matches"] == []


def test_application_http_duplicate_precheck_and_acknowledgement_contract(
    api_paused, services
) -> None:
    """Duplicate acknowledgement precedes every write, and the retry keeps its warnings.

    The retry differs from the original only in whitespace and case, so each of the
    three match reasons is found through normalisation rather than byte equality.
    """
    payload = {
        "company": "HTTP Duplicate Co",
        "target_role": "Developer",
        "job_text": "Duplicate HTTP text",
        "source_url": "https://jobs.example/http-duplicate",
    }
    variant = {
        **payload,
        "company": " http duplicate  co ",
        "target_role": "DEVELOPER",
        "job_text": "Duplicate  HTTP\ntext",
    }
    api = api_paused.client
    original = api.post(
        f"{API_PREFIX}/applications",
        headers=MUTATION_HEADERS,
        json=payload,
    )
    assert original.status_code == 201
    expected_matches = [
        {
            "application_id": original.json()["application_id"],
            "company": "HTTP Duplicate Co",
            "target_role": "Developer",
            "matched_on": ["source_url", "normalized_text", "company_title"],
        }
    ]

    checked = api.post(
        f"{API_PREFIX}/applications/duplicate-check",
        headers=MUTATION_HEADERS,
        json=variant,
    )
    assert checked.status_code == 200
    assert checked.json()["matches"] == expected_matches

    listed_before = api.get(f"{API_PREFIX}/applications").json()["items"]
    refused = api.post(
        f"{API_PREFIX}/applications",
        headers=MUTATION_HEADERS,
        json=variant,
    )
    assert refused.status_code == 412
    assert refused.json()["code"] == "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED"
    assert refused.json()["context"]["matches"] == expected_matches
    assert api.get(f"{API_PREFIX}/applications").json()["items"] == listed_before
    assert len(listed_before) == 1

    accepted = api.post(
        f"{API_PREFIX}/applications",
        headers=MUTATION_HEADERS,
        json={**variant, "acknowledged_duplicates": True},
    )
    assert accepted.status_code == 201
    assert accepted.json()["warnings"] == [
        "DUPLICATE_SOURCE_URL",
        "DUPLICATE_NORMALIZED_TEXT",
        "DUPLICATE_COMPANY_TITLE",
    ]
    assert len(api.get(f"{API_PREFIX}/applications").json()["items"]) == 2
    creation_event = api.get(
        f"{API_PREFIX}/applications/{accepted.json()['application_id']}"
    ).json()["recruitment_timeline"][0]
    assert creation_event["actor_type"] == "user"
    assert creation_event["client"] == "web"
    base = {
        "company": "URL Safety Co",
        "target_role": "Developer",
        "job_text": "A safe posting",
    }
    for field, value in (
        ("company", "unsafe company\u0000"),
        ("target_role", "unsafe role\u0000"),
        ("job_text", "unsafe posting\u0000"),
        ("source_url", "https://jobs.example/unsafe\u0000"),
    ):
        for endpoint in ("applications/duplicate-check", "applications"):
            controlled = api.post(
                f"{API_PREFIX}/{endpoint}",
                headers=MUTATION_HEADERS,
                json={**base, field: value},
            )
            assert controlled.status_code == 412
            assert controlled.json()["code"] == "APPLICATION_INTAKE_INVALID"
            assert controlled.json()["context"] == {"field": field}
            assert value not in controlled.json()["detail"]
    assert len(api.get(f"{API_PREFIX}/applications").json()["items"]) == 2
    too_long = api.post(
        f"{API_PREFIX}/applications/duplicate-check",
        headers=MUTATION_HEADERS,
        json={**base, "source_url": "https://jobs.example/" + "x" * 2048},
    )

    assert too_long.status_code == 422


def test_application_list_query_narrows_orders_and_pages_at_the_boundary(
    api_paused, services
) -> None:
    """The list query is answered by the application layer; the router only maps it.

    What is under test here is that mapping: the parameters reach the query, the
    counts come back beside the page, and a value outside the closed sets or the
    paging bounds is refused at the boundary rather than silently matching nothing.
    """
    api = api_paused.client
    for company in ("Alpha", "Binat", "Cegal"):
        created = api.post(
            f"{API_PREFIX}/applications",
            headers=MUTATION_HEADERS,
            json={
                "company": company,
                "target_role": "Developer",
                "job_text": f"A posting from {company}",
            },
        )
        assert created.status_code == 201
        if company == "Cegal":
            closed_id = created.json()["application_id"]

    closed = api.post(f"{API_PREFIX}/applications/{closed_id}/close", headers=MUTATION_HEADERS)
    assert closed.status_code == 200

    whole = api.get(f"{API_PREFIX}/applications").json()
    assert (whole["matched"], whole["total"]) == (3, 3)
    assert whole["limit"] is None and whole["offset"] == 0
    # Every row is at the first stage, and a state nothing reached is absent
    # rather than reported as zero.
    assert whole["stage_counts"] == {"needs_analysis": 3}
    assert whole["preset_counts"] == {
        "all": 3,
        "needs_attention": 0,
        "ready_to_send": 0,
        "active_interviews": 0,
    }
    assert whole["recruitment_status_counts"] == {"saved": 2, "closed": 1}
    assert {item["company"]: item["is_closed"] for item in whole["items"]} == {
        "Alpha": False,
        "Binat": False,
        "Cegal": True,
    }

    # A closed Application stays stored and reachable, and is not what a board
    # of live work is asking about.
    live = api.get(f"{API_PREFIX}/applications", params={"activity": "open"}).json()
    assert sorted(item["company"] for item in live["items"]) == ["Alpha", "Binat"]
    assert (live["matched"], live["total"]) == (2, 3)

    found = api.get(f"{API_PREFIX}/applications", params={"search": "binat"}).json()
    assert [item["company"] for item in found["items"]] == ["Binat"]

    # Every row is at the first stage here, so the filter that names it keeps
    # them and one that names another stage keeps none - both from the computed
    # projection rather than a stored column.
    staged = api.get(f"{API_PREFIX}/applications", params={"stage": ["needs_analysis"]}).json()
    assert staged["matched"] == 3
    # Counted before narrowing: a stage filter must not erase its own options.
    assert staged["stage_counts"] == {"needs_analysis": 3}
    assert api.get(f"{API_PREFIX}/applications", params={"stage": ["ready"]}).json()["matched"] == 0

    ordered = api.get(f"{API_PREFIX}/applications", params={"sort": "company"}).json()
    assert [item["company"] for item in ordered["items"]] == ["Alpha", "Binat", "Cegal"]

    page = api.get(
        f"{API_PREFIX}/applications",
        params={"sort": "company", "limit": 2, "offset": 1},
    ).json()
    assert [item["company"] for item in page["items"]] == ["Binat", "Cegal"]
    # The page is what it holds; the counts are what place it.
    assert (page["matched"], page["total"]) == (3, 3)
    assert (page["limit"], page["offset"]) == (2, 1)

    # A stale page number is an empty page, not a refusal.
    past_end = api.get(f"{API_PREFIX}/applications", params={"offset": 50}).json()
    assert past_end["items"] == [] and past_end["matched"] == 3

    for params in (
        {"activity": "archived"},
        {"stage": ["not_a_stage"]},
        {"sort": "whatever"},
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
    ):
        refused = api.get(f"{API_PREFIX}/applications", params=params)
        assert refused.status_code == 422, params
