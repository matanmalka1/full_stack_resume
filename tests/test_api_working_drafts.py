"""M3 Stage E: the WorkingDraft surface, and the corrected validate/approve contract.

Two things here are corrections rather than additions, and they are what the
file is really about.

`validate_draft` and `approve_draft` now name the exact draft version and the
exact ValidationRun. Approval used to validate for itself, which meant §15's
four binding conditions compared a run against the draft that had just produced
it: they could not fail, so they proved nothing. Against a run the user obtained
earlier they are real, and the tests that matter here are the ones where they
fail - an edit after validation, a run from another draft, a run that did not
pass.

The second is the ETag. Two saves carrying the same token is the concurrency
matrix's first row, and the second one has to change nothing at all - not
"win", not "merge", not "bump the version anyway".
"""

from __future__ import annotations

import json

from api_harness import MUTATION_HEADERS
from helpers import ACCOUNT_MANAGER_JOB, run_cli, working_claim

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand

UNSUPPORTED_WORDING = "Delivered 30% improvement in direct SaaS Sales."


def _application(services, company: str) -> str:
    return services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    ).application_id


def _post(harness, path: str, body: dict, **headers) -> object:
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body, headers={**MUTATION_HEADERS, **headers}
    )


def _analyze(harness, application_id: str) -> dict[str, str]:
    detail = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert detail.status_code == 200, detail.text
    response = _post(
        harness,
        f"/applications/{application_id}/analyses",
        {"job_snapshot_id": detail.json()["active_job_snapshot_id"]},
    )
    assert response.status_code == 202, response.text
    finished = harness.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    return {output["output_type"]: output["output_id"] for output in finished["outputs"]}


def _generate(harness, application_id: str, sources: dict[str, str]) -> str:
    response = _post(
        harness,
        f"/applications/{application_id}/working-draft/generate",
        {
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
        },
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    finished = harness.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    outputs = {output["output_type"]: output["output_id"] for output in finished["outputs"]}
    return outputs["working_draft"]


def _drafted(harness, company: str) -> tuple[str, str, dict[str, str]]:
    """An Application through analyze and generate, over HTTP only."""
    application_id = _application(harness.services, company)
    sources = _analyze(harness, application_id)
    return application_id, _generate(harness, application_id, sources), sources


def _read(harness, working_draft_id: str):
    response = harness.client.get(f"{API_PREFIX}/working-drafts/{working_draft_id}")
    assert response.status_code == 200, response.text
    return response


def _patch(harness, working_draft_id: str, etag: str, claim_edits: list[dict]):
    return harness.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_edits": claim_edits},
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )


def _state(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _audit(harness, application_id: str, action: str) -> dict:
    """The one audit record for this action, or an assertion naming what is there."""
    records = [
        record
        for record in harness.services.repository.audit_records(application_id)
        if record["action"] == action
    ]
    assert len(records) == 1, records
    return records[0]


def _unsupported_edit(harness, application_id: str) -> dict:
    """One claim rewritten into wording no fact authorizes."""
    claim = working_claim(harness.services, application_id, "sales.metric.performance")
    return {"claim_id": claim.claim_id, "fact_ids": [], "text": UNSUPPORTED_WORDING}


# --- E1: generation ----------------------------------------------------------


# --- E2: read, ETag, and optimistic update -----------------------------------


def test_a_second_save_with_the_same_etag_is_a_conflict_that_changes_nothing(api_worker) -> None:
    """The concurrency matrix's first row: two autosaves, one ETag.

    The assertion that matters is the third one. A `409` that had already
    written would be worse than no check at all, because the client would be
    told its save failed while the document moved underneath it.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Same Etag Co")
    read = _read(api_worker, working_draft_id)
    claim = working_claim(api_worker.services, application_id, "sales.metric.performance")
    edits = [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}]
    first = _patch(api_worker, working_draft_id, read.headers["ETag"], edits)
    assert first.status_code == 200, first.text

    second = _patch(api_worker, working_draft_id, read.headers["ETag"], edits)

    assert second.status_code == 409, second.text
    assert second.json()["code"] == "STATE_CONFLICT"
    after = _read(api_worker, working_draft_id).json()
    assert after["edit_version"] == first.json()["edit_version"]
    assert after["content_hash"] == first.json()["content_hash"]


def test_cli_edit_wins_before_a_web_autosave_with_the_stale_etag(api_worker) -> None:
    """The two clients share the same optimistic draft version, not two stores."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "CLI Web Race Co")
    read = _read(api_worker, working_draft_id)
    claim = working_claim(api_worker.services, application_id, "sales.metric.performance")
    before = read.json()

    edited = run_cli(
        "--workspace",
        str(api_worker.services.workspace.root),
        "edit-claim",
        application_id,
        claim.claim_id,
        "--text",
        claim.text,
        "--fact-id",
        claim.fact_ids[0],
    )
    assert edited.returncode == 0, edited.stderr
    cli_version = _read(api_worker, working_draft_id).json()
    assert cli_version["edit_version"] == before["edit_version"] + 1

    stale_web = _patch(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}],
    )
    assert stale_web.status_code == 409, stale_web.text
    assert stale_web.json()["code"] == "STATE_CONFLICT"
    after = _read(api_worker, working_draft_id).json()
    assert (after["edit_version"], after["content_hash"]) == (
        cli_version["edit_version"],
        cli_version["content_hash"],
    )


def test_free_text_no_fact_authorizes_is_kept_as_a_pending_claim(api_worker) -> None:
    """§14: unauthorized free text is saved, not discarded and not refused."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Pending Text Co")
    read = _read(api_worker, working_draft_id)
    edit = _unsupported_edit(api_worker, application_id)

    response = _patch(api_worker, working_draft_id, read.headers["ETag"], [edit])

    assert response.status_code == 200, response.text
    assert response.json()["pending_claim_ids"] == [edit["claim_id"]]
    stored = _read(api_worker, working_draft_id).json()["source"]
    saved = next(
        claim
        for section in stored["sections"]
        for claim in section["claims"]
        if claim["claim_id"] == edit["claim_id"]
    )
    assert saved["claim_type"] == "pending"
    assert saved["text"] == UNSUPPORTED_WORDING
    assert saved["pending_reason"]


# --- E3: selection change, archive, replace ----------------------------------


def test_a_selection_change_creates_a_plan_and_moves_the_draft_onto_it(api_worker) -> None:
    """§14: one immutable SelectionPlan, and the draft rebuilt from it."""
    application_id, working_draft_id, sources = _drafted(api_worker, "Reselection Co")
    before = _read(api_worker, working_draft_id).json()
    # A Core Skills fact that the engine selected: excluding one of those does
    # not cost a role block its floor or empty a required tag, which are the
    # two exclusions the domain refuses outright.
    excluded = next(
        candidate["fact_id"]
        for candidate in before["source"]["selection"]["candidates"]
        if candidate["section"] == "Core Skills" and candidate["outcome"] == "selected"
    )

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/apply-selection-change",
        {"expected_edit_version": before["edit_version"], "excluded_fact_ids": [excluded]},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["selection_plan_id"] != sources["selection_plan"]
    assert body["edit_version"] == before["edit_version"] + 1
    after = _read(api_worker, working_draft_id).json()
    assert after["selection_plan_id"] == body["selection_plan_id"]
    assert excluded not in after["source"]["selected_fact_ids"]
    assert after["source"]["omitted_facts"][excluded] == "excluded_by_user"


def test_a_selection_change_refuses_a_draft_carrying_manual_wording(api_worker) -> None:
    """§14's other branch: a deterministic rebuild would discard the user's text."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Manual Wording Co")
    read = _read(api_worker, working_draft_id)
    edited = _patch(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [_unsupported_edit(api_worker, application_id)],
    )
    assert edited.status_code == 200, edited.text

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/apply-selection-change",
        {"expected_edit_version": edited.json()["edit_version"], "excluded_fact_ids": []},
    )

    assert response.status_code == 412, response.text
    assert "regenerate_section" in response.json()["detail"]
    after = _read(api_worker, working_draft_id).json()
    assert after["edit_version"] == edited.json()["edit_version"]


def test_archiving_registers_the_snapshot_before_clearing_the_pointer(api_worker) -> None:
    """§14: the historical record exists first, and the payload is really there."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Archive Co")
    before = _read(api_worker, working_draft_id).json()

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/archive",
        {"expected_edit_version": before["edit_version"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    artifacts = api_worker.client.get(f"{API_PREFIX}/applications/{application_id}/artifacts")
    registered = next(
        item for item in artifacts.json()["items"] if item["id"] == body["artifact_version_id"]
    )
    assert registered["artifact_type"] == "working_draft_snapshot"
    assert registered["lifecycle_status"] == "archived"
    assert registered["metadata"]["working_draft_id"] == working_draft_id
    assert _audit(api_worker, application_id, "archive_working_draft")["client"] == "web"
    stored = api_worker.services.artifacts.resolve(
        api_worker.services.repository.artifact_version(body["artifact_version_id"])["path"]
    )
    assert json.loads(stored.read_text(encoding="utf-8"))["application_id"] == application_id
    state = _state(api_worker, application_id)
    assert state["active_working_draft_id"] is None
    assert state["working_draft_state"] == "none"


def test_replacement_keeps_the_previous_draft_when_the_user_asked_to(api_worker) -> None:
    """§14 Keep: the snapshot is materialized, and the draft is replaced in place."""
    application_id, working_draft_id, sources = _drafted(api_worker, "Replace Keep Co")
    before = _read(api_worker, working_draft_id).json()

    response = _post(
        api_worker,
        f"/applications/{application_id}/working-draft/replace",
        {
            "working_draft_id": working_draft_id,
            "expected_edit_version": before["edit_version"],
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            "keep_previous": True,
        },
    )

    assert response.status_code == 202, response.text
    finished = api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    after = _read(api_worker, working_draft_id).json()
    assert after["edit_version"] == before["edit_version"] + 1
    assert after["active"] is True
    artifacts = api_worker.client.get(f"{API_PREFIX}/applications/{application_id}/artifacts")
    kept = [
        item
        for item in artifacts.json()["items"]
        if item["artifact_type"] == "working_draft_snapshot"
    ]
    assert [item["metadata"]["edit_version"] for item in kept] == [before["edit_version"]]
    assert _audit(api_worker, application_id, "replace_working_draft")["client"] == "web"


def test_a_refused_replacement_leaves_the_existing_draft_exactly_as_it_was(api_worker) -> None:
    """§14: nothing is deleted or deactivated before the replacement succeeds."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Replace Refusal Co")
    other_id = _application(api_worker.services, "Replace Refusal Other Co")
    other_sources = _analyze(api_worker, other_id)
    before = _read(api_worker, working_draft_id).json()

    response = _post(
        api_worker,
        f"/applications/{application_id}/working-draft/replace",
        {
            "working_draft_id": working_draft_id,
            "expected_edit_version": before["edit_version"],
            "job_analysis_id": other_sources["job_analysis"],
            "selection_plan_id": other_sources["selection_plan"],
        },
    )

    assert response.status_code == 412, response.text
    assert _read(api_worker, working_draft_id).json() == before
    assert _state(api_worker, application_id)["active_working_draft_id"] == working_draft_id


# --- E4: validation ----------------------------------------------------------


def test_a_failed_validation_is_a_successful_outcome_with_its_run_recorded(api_worker) -> None:
    """§22: `passed=false` is `200`, and the immutable run is written anyway."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Failing Validation Co")
    read = _read(api_worker, working_draft_id)
    edited = _patch(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [_unsupported_edit(api_worker, application_id)],
    )

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": edited.json()["edit_version"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is False
    assert any(issue["code"] == "pending-claim" for issue in body["report"]["issues"])
    assert api_worker.services.repository.validation_report(body["validation_run_id"]).passed is (
        False
    )
    assert _state(api_worker, application_id)["working_draft_state"] == "validation_failed"
    stale = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": body["edit_version"] + 1},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "STATE_CONFLICT"


# --- E5: approval ------------------------------------------------------------


def _validated(harness, working_draft_id: str) -> dict:
    read = _read(harness, working_draft_id).json()
    response = _post(
        harness,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": read["edit_version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_an_edit_after_validation_makes_that_run_unusable_for_approval(api_worker) -> None:
    """The binding check that could not fail before, failing.

    Approval used to validate for itself, so the run always described the draft
    in front of it. Here the run is real evidence about an earlier version, and
    approving against it would freeze content nothing checked.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Stale Approval Co")
    validated = _validated(api_worker, working_draft_id)
    read = _read(api_worker, working_draft_id)
    claim = working_claim(api_worker.services, application_id, "sales.metric.performance")
    edited = _patch(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}],
    )
    assert edited.status_code == 200, edited.text

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": edited.json()["edit_version"],
            "validation_run_id": validated["validation_run_id"],
        },
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "VALIDATION_STALE"
    assert api_worker.services.repository.approved_revisions(application_id) == []


def test_a_failing_run_blocks_approval_and_says_which_groups_failed(api_worker) -> None:
    application_id, working_draft_id, _sources = _drafted(api_worker, "Blocked Approval Co")
    read = _read(api_worker, working_draft_id)
    edited = _patch(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [_unsupported_edit(api_worker, application_id)],
    )
    failed = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": edited.json()["edit_version"]},
    ).json()
    assert failed["passed"] is False

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": failed["edit_version"],
            "validation_run_id": failed["validation_run_id"],
        },
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "VALIDATION_BLOCKED"
    assert response.json()["context"]["issue_count"] >= 1


def test_the_same_key_returns_the_same_revision_and_a_changed_payload_is_reuse(
    api_worker,
) -> None:
    """§15: the payload covers all three arguments plus the content hash."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Approval Key Co")
    validated = _validated(api_worker, working_draft_id)
    body = {
        "expected_edit_version": validated["edit_version"],
        "validation_run_id": validated["validation_run_id"],
    }

    first = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        body,
        **{"Idempotency-Key": "approve-once"},
    )
    repeated = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        body,
        **{"Idempotency-Key": "approve-once"},
    )

    assert first.status_code == 201, first.text
    assert repeated.json() == first.json()
    assert len(api_worker.services.repository.approved_revisions(application_id)) == 1

    _other_app, other_draft_id, _other = _drafted(api_worker, "Approval Key Other Co")
    other = _validated(api_worker, other_draft_id)
    reused = _post(
        api_worker,
        f"/working-drafts/{other_draft_id}/approve",
        {
            "expected_edit_version": other["edit_version"],
            "validation_run_id": other["validation_run_id"],
        },
        **{"Idempotency-Key": "approve-once"},
    )

    assert reused.status_code == 409, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


# --- E6: CLI compatibility ---------------------------------------------------


def test_cv_validate_prints_the_run_id_and_cv_approve_consumes_it(
    drafted_application, cli_runner
) -> None:
    """The CLI resolves the run at its own boundary and approval verifies it."""
    setup = drafted_application("CLI Validate Co")

    validated = cli_runner("validate", setup.application_id)
    approved = cli_runner("approve", setup.application_id)

    assert validated.returncode == 0, validated.stderr
    run_id = json.loads(validated.stdout)["validation_run_id"]
    assert json.loads(validated.stdout)["passed"] is True
    assert approved.returncode == 0, approved.stderr
    revision = setup.services.repository.approved_revision(
        json.loads(approved.stdout)["revision_id"]
    )
    assert revision.validation_run_id == run_id
    # The other half of the provenance contract: the CLI still records `cli`.
    # Asserted here rather than in a case of its own, because this is the test
    # that already approves through the CLI.
    assert revision.decision_provenance["client"] == "cli"


def test_cv_approve_refuses_when_no_run_describes_the_current_draft(
    drafted_application, cli_runner
) -> None:
    """The observable CLI change, stated as a refusal that names the next step."""
    setup = drafted_application("CLI Approve Refusal Co")
    services, application_id = setup.services, setup.application_id
    working = services.repository.active_working_draft(application_id)
    claim = working_claim(services, application_id, "sales.metric.performance")
    from cv_engine.application.commands import ClaimPatch, UpdateWorkingDraftCommand

    services.drafts.update_working_draft(
        UpdateWorkingDraftCommand(
            working_draft_id=working.id,
            expected_edit_version=working.edit_version,
            expected_content_hash=working.content_hash,
            claim_edits=[
                ClaimPatch(claim_id=claim.claim_id, fact_ids=claim.fact_ids, text=claim.text)
            ],
        )
    )

    approved = cli_runner("approve", application_id)

    assert approved.returncode == 2
    assert "cv validate" in approved.stderr
    assert services.repository.approved_revisions(application_id) == []
