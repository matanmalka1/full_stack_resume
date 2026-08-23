"""M3 §5.4 item 1: the whole sequence, through the API, offline.

Create -> Analyze -> Draft -> Edit -> Validate -> Approve -> Render -> Ready,
driven entirely over HTTP against a real FastAPI app, a real `OperationWorker`,
real SQLite, and a real filesystem. This is the acceptance test the milestone
names, so it is deliberately one long test rather than several short ones: what
is being proved is that the steps compose, and a suite that proved each step
separately would not have proved that.

**`OPENAI_API_KEY` is asserted unset inside the test.** Not arranged - asserted.
The deterministic slice must reach Ready with no provider configured, and a test
that merely happened to run without a key would stop proving that the day a
developer exported one.

Three things it does *not* do, each for a stated reason:

- It does not stub the application layer anywhere. The only substitution is the
  browser, through `deterministic_renderer`, because Playwright is blocked by
  the OS sandbox this suite runs under; the render service, its Operation
  handler, and every registration are the real ones.
- It does not read the repository to decide what happened next. Every step is
  driven from the previous response, because that is what a client has.
- It does not skip the edit. §23's sequence has an Edit step, and a journey that
  went straight from draft to validate would leave the ETag path unproven in the
  one test that is meant to prove the path end to end.
"""

from __future__ import annotations

import os

from api_harness import MUTATION_HEADERS
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB, working_claim

from cv_engine.api.app import API_PREFIX


def _post(harness, path: str, body: dict | None = None, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body or {}, headers={**MUTATION_HEADERS, **headers}
    )


def _patch(harness, path: str, body: dict, **headers):
    return harness.client.patch(
        f"{API_PREFIX}{path}", json=body, headers={**MUTATION_HEADERS, **headers}
    )


def _get(harness, path: str):
    return harness.client.get(f"{API_PREFIX}{path}")


def _run_operation(harness, response, *, expect: str = "succeeded") -> dict:
    """Assert the `202` contract, then let the real worker finish the work."""
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert response.headers["Location"].endswith(accepted["id"])
    finished = harness.wait_for_operation(accepted["id"])
    assert finished["status"] == expect, finished
    return finished


def _outputs(finished: dict) -> dict[str, str]:
    return {output["output_type"]: output["output_id"] for output in finished["outputs"]}


def test_the_full_api_journey_reaches_ready_offline(
    api_worker, deterministic_renderer, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert os.environ.get("OPENAI_API_KEY") is None, (
        "the deterministic slice must reach Ready with no provider configured"
    )

    # --- Create ---------------------------------------------------------
    created = _post(
        api_worker,
        "/applications",
        {
            "company": "Journey Co",
            "target_role": "Account Manager",
            "job_text": ACCOUNT_MANAGER_JOB,
            "acknowledged_duplicates": True,
        },
    )
    assert created.status_code == 201, created.text
    application_id = created.json()["application_id"]
    job_snapshot_id = created.json()["job_snapshot_id"]

    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "needs_analysis"

    # --- Analyze --------------------------------------------------------
    analyzed = _run_operation(
        api_worker,
        _post(
            api_worker,
            f"/applications/{application_id}/analyses",
            {"job_snapshot_id": job_snapshot_id},
        ),
    )
    sources = _outputs(analyzed)
    analysis_id = sources["job_analysis"]
    # §5.4 item 2: Analyze commits the initial deterministic SelectionPlan, so
    # the no-review path can draft without a separate selection command.
    selection_plan_id = sources["selection_plan"]

    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "ready_to_draft"
    assert detail["active_selection_plan_id"] == selection_plan_id

    # --- Draft ----------------------------------------------------------
    drafted = _run_operation(
        api_worker,
        _post(
            api_worker,
            f"/applications/{application_id}/working-draft/generate",
            {"job_analysis_id": analysis_id, "selection_plan_id": selection_plan_id},
        ),
    )
    working_draft_id = _outputs(drafted)["working_draft"]

    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "ready_for_approval"
    assert detail["working_draft_state"] == "validated"

    read = _get(api_worker, f"/working-drafts/{working_draft_id}")
    assert read.status_code == 200, read.text
    etag = read.headers["ETag"]

    # --- Edit -----------------------------------------------------------
    # A real claim edit, restating one claim's own facts and wording. The patch
    # has to carry at least one claim - `claim_edits` is `min_length=1`, because
    # a save that changes nothing is not an edit - so the journey makes the
    # smallest genuine one rather than an empty request the API rejects.
    #
    # It still commits a new version: `apply_claim_edit` records the manual
    # derivation, so the content hash moves even when the words do not, which is
    # what makes the second save below a real lost-update attempt.
    claim = working_claim(api_worker.services, application_id, "sales.metric.performance")
    patch_body = {
        "claim_edits": [
            {"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}
        ]
    }

    edited = _patch(
        api_worker, f"/working-drafts/{working_draft_id}", patch_body, **{"If-Match": etag}
    )
    assert edited.status_code == 200, edited.text
    new_etag = edited.headers["ETag"]
    assert new_etag != etag

    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "draft_in_progress"
    assert detail["working_draft_state"] == "editing"

    # The same token again is the concurrency matrix's first row: the second
    # save must change nothing at all rather than win or merge.
    stale = _patch(
        api_worker, f"/working-drafts/{working_draft_id}", patch_body, **{"If-Match": etag}
    )
    assert stale.status_code == 409, stale.text
    assert _get(api_worker, f"/working-drafts/{working_draft_id}").headers["ETag"] == new_etag

    # --- Validate -------------------------------------------------------
    current = _get(api_worker, f"/working-drafts/{working_draft_id}").json()
    validated = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": current["edit_version"]},
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["passed"] is True, validated.json()["report"]
    validation_run_id = validated.json()["validation_run_id"]

    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "ready_for_approval"
    assert detail["working_draft_state"] == "validated"

    # --- Approve --------------------------------------------------------
    approved = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": current["edit_version"],
            "validation_run_id": validation_run_id,
        },
    )
    assert approved.status_code == 201, approved.text
    revision_id = approved.json()["revision_id"]

    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "approved"

    revision = _get(api_worker, f"/approved-revisions/{revision_id}").json()
    assert revision["ready_qualified"] is False, "nothing is rendered yet"
    # The approval was made from a browser, and the immutable record must say so.
    assert revision["decision_provenance"]["client"] == "web"

    # --- Render ---------------------------------------------------------
    rendered = _run_operation(
        api_worker,
        _post(
            api_worker,
            f"/approved-revisions/{revision_id}/render",
            {"application_id": application_id},
        ),
    )
    pdf_artifact_version_id = _outputs(rendered)["resume_pdf"]

    # --- Ready ----------------------------------------------------------
    detail = _get(api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "ready"
    assert detail["latest_ready_revision_id"] == revision_id

    revision = _get(api_worker, f"/approved-revisions/{revision_id}").json()
    assert revision["ready_qualified"] is True
    assert revision["pdf_artifact_version_id"] == pdf_artifact_version_id
    assert revision["ready_validation"]["passed"] is True

    # --- Download the exact Ready PDF (§5.2) ----------------------------
    export = _get(
        api_worker,
        f"/approved-revisions/{revision_id}/recruiter-pdf"
        f"?pdf_artifact_version_id={pdf_artifact_version_id}",
    )
    assert export.status_code == 200, export.text
    assert export.content.startswith(b"%PDF")
    assert "CV.pdf" in export.headers["content-disposition"]

    by_id = _get(api_worker, f"/artifacts/{pdf_artifact_version_id}/download")
    assert by_id.status_code == 200, by_id.text
    assert by_id.content == export.content


def test_the_review_journey_resolves_once_and_reaches_ready(
    api_worker, deterministic_renderer
) -> None:
    created = _post(
        api_worker,
        "/applications",
        {
            "company": "Review Journey Co",
            "target_role": "Account Manager",
            "job_text": AMBIGUOUS_HEBREW_JOB,
            "acknowledged_duplicates": True,
        },
    )
    assert created.status_code == 201, created.text
    application_id = created.json()["application_id"]

    analyzed = _run_operation(
        api_worker,
        _post(
            api_worker,
            f"/applications/{application_id}/analyses",
            {"job_snapshot_id": created.json()["job_snapshot_id"]},
        ),
    )
    original = _outputs(analyzed)
    state = _get(api_worker, f"/applications/{application_id}").json()
    assert state["preparation_state"] == "needs_review"
    assert state["recommended_action"] == "apply_analysis_decisions"

    decided = _post(
        api_worker,
        f"/analyses/{original['job_analysis']}/apply-decisions",
        {
            "application_id": application_id,
            "profile_override": "account-manager",
            "accept_low_fit": True,
        },
    )
    assert decided.status_code == 201, decided.text
    resolved = decided.json()
    assert resolved["created_analysis"] is True
    assert resolved["job_analysis_id"] != original["job_analysis"]
    assert resolved["selection_plan_id"] != original["selection_plan"]
    state = _get(api_worker, f"/applications/{application_id}").json()
    assert state["review_reasons"] == []
    assert state["preparation_state"] == "ready_to_draft"

    drafted = _run_operation(
        api_worker,
        _post(
            api_worker,
            f"/applications/{application_id}/working-draft/generate",
            {
                "job_analysis_id": resolved["job_analysis_id"],
                "selection_plan_id": resolved["selection_plan_id"],
            },
        ),
    )
    working_draft_id = _outputs(drafted)["working_draft"]
    working = _get(api_worker, f"/working-drafts/{working_draft_id}").json()

    validated = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": working["edit_version"]},
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["passed"] is True

    approved = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": working["edit_version"],
            "validation_run_id": validated.json()["validation_run_id"],
        },
    )
    assert approved.status_code == 201, approved.text
    revision_id = approved.json()["revision_id"]

    rendered = _run_operation(
        api_worker,
        _post(
            api_worker,
            f"/approved-revisions/{revision_id}/render",
            {"application_id": application_id},
        ),
    )
    assert _outputs(rendered)["resume_pdf"]
    state = _get(api_worker, f"/applications/{application_id}").json()
    assert state["preparation_state"] == "ready"
    assert state["latest_ready_revision_id"] == revision_id
