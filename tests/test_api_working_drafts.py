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
from helpers import ACCOUNT_MANAGER_JOB, working_claim

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand
from cv_engine.domain.models import ValidationIssue, ValidationReport

UNSUPPORTED_WORDING = "Delivered 30% improvement in direct SaaS Sales."


def _application(services, company: str) -> str:
    return services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
            client="web",
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


def _remove(harness, working_draft_id: str, etag: str, claim_removals: list[str]):
    return harness.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_removals": claim_removals},
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


def test_generation_records_the_explicit_parent_approved_revision(api_worker) -> None:
    application_id, working_draft_id, sources = _drafted(api_worker, "Parent Revision Co")
    validated = _validated(api_worker, working_draft_id)
    approved = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": validated["edit_version"],
            "validation_run_id": validated["validation_run_id"],
        },
    )
    assert approved.status_code == 201, approved.text

    queued = _post(
        api_worker,
        f"/applications/{application_id}/working-draft/generate",
        {
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            "parent_revision_id": approved.json()["revision_id"],
        },
    )
    assert queued.status_code == 202, queued.text
    finished = api_worker.wait_for_operation(queued.json()["id"])
    assert finished["status"] == "succeeded", finished
    draft_id = next(
        output["output_id"]
        for output in finished["outputs"]
        if output["output_type"] == "working_draft"
    )
    assert (
        _read(api_worker, draft_id).json()["parent_revision_id"] == approved.json()["revision_id"]
    )


def test_generation_refuses_a_parent_revision_owned_by_another_application(
    api_worker,
) -> None:
    first_id, first_draft, _first_sources = _drafted(api_worker, "Parent Owner Co")
    validated = _validated(api_worker, first_draft)
    approved = _post(
        api_worker,
        f"/working-drafts/{first_draft}/approve",
        {
            "expected_edit_version": validated["edit_version"],
            "validation_run_id": validated["validation_run_id"],
        },
    )
    assert approved.status_code == 201, approved.text

    second_id = _application(api_worker.services, "Parent Intruder Co")
    second_sources = _analyze(api_worker, second_id)
    queued = _post(
        api_worker,
        f"/applications/{second_id}/working-draft/generate",
        {
            "job_analysis_id": second_sources["job_analysis"],
            "selection_plan_id": second_sources["selection_plan"],
            "parent_revision_id": approved.json()["revision_id"],
        },
    )

    assert queued.status_code == 412, queued.text
    assert queued.json()["code"] == "LINEAGE_BROKEN"
    assert (
        api_worker.services.repository.approved_revision(
            approved.json()["revision_id"]
        ).application_id
        == first_id
    )
    assert _state(api_worker, second_id)["active_working_draft_id"] is None


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


def test_an_out_of_band_edit_wins_before_a_web_autosave_with_the_stale_etag(
    api_worker,
) -> None:
    """Every writer shares one optimistic draft version, not a store of its own.

    The edit here goes through the draft service directly, the way a
    maintenance path or a second Web session reaches it. What the test pins is
    that the Web autosave holding the now-stale ETag is refused rather than
    silently overwriting the newer version.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Draft Race Co")
    read = _read(api_worker, working_draft_id)
    claim = working_claim(api_worker.services, application_id, "sales.metric.performance")
    before = read.json()

    api_worker.services.drafts.edit_claim(
        application_id,
        claim.claim_id,
        [claim.fact_ids[0]],
        text=claim.text,
    )
    out_of_band = _read(api_worker, working_draft_id).json()
    assert out_of_band["edit_version"] == before["edit_version"] + 1

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
        out_of_band["edit_version"],
        out_of_band["content_hash"],
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


# --- M4 Stage D: the editor's read, its preview, and claim removal -----------


def test_the_draft_read_carries_an_outline_the_editor_can_address(api_worker) -> None:
    """The outline is derived from the same document `source` carries.

    Asserted against `source` rather than against a fixture, because the claim
    that matters is that the two cannot disagree: the outline is computed per
    read from that object, not stored beside it.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Outline Co")
    body = _read(api_worker, working_draft_id).json()
    outline, source = body["outline"], body["source"]

    assert outline["headline"]["claim_id"] == source["headline"]["claim_id"]
    assert [claim["claim_id"] for claim in outline["contacts"]] == [
        claim["claim_id"] for claim in source["contacts"]
    ]
    assert [section["name"] for section in outline["sections"]] == [
        section["name"] for section in source["sections"]
    ]
    outlined = {
        claim["claim_id"]: claim for section in outline["sections"] for claim in section["claims"]
    }
    stored = {
        claim["claim_id"]: claim for section in source["sections"] for claim in section["claims"]
    }
    assert set(outlined) == set(stored)
    for claim_id, claim in outlined.items():
        assert (claim["text"], claim["claim_type"], claim["style"]) == (
            stored[claim_id]["text"],
            stored[claim_id]["claim_type"],
            stored[claim_id]["style"],
        )
        assert claim["fact_ids"] == stored[claim_id]["fact_ids"]


def test_the_facts_read_is_the_union_of_linked_facts_and_plan_candidates(api_worker) -> None:
    """Neither set covers the other, which is the whole reason for this read.

    Contacts come from the candidate context and appear in no SelectionPlan; an
    omitted candidate appears in no claim. A read that returned only one of them
    would leave the editor unable to say either what backs a line or what could
    be added to one.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Fact Union Co")
    draft = _read(api_worker, working_draft_id).json()
    response = api_worker.client.get(f"{API_PREFIX}/working-drafts/{working_draft_id}/facts")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language"] == draft["source"]["language"]
    rows = {row["fact_id"]: row for row in body["facts"]}

    contact_fact = draft["source"]["contacts"][0]["fact_ids"][0]
    assert contact_fact in rows, "a contact's fact is linked but is not a plan candidate"
    assert rows[contact_fact]["outcome"] is None
    assert rows[contact_fact]["linked_claim_ids"] == [draft["source"]["contacts"][0]["claim_id"]]

    omitted = next(
        candidate["fact_id"]
        for candidate in draft["source"]["selection"]["candidates"]
        if candidate["outcome"] == "omitted"
    )
    assert omitted in rows, "an omitted candidate is in no claim and must still be offered"
    assert rows[omitted]["linked_claim_ids"] == []
    assert rows[omitted]["reason"]

    # Every row a claim links names that claim, and reads as text rather than
    # as the identifier the M4 gate says a user must never need.
    for section in draft["source"]["sections"]:
        for claim in section["claims"]:
            for fact_id in claim["fact_ids"]:
                assert claim["claim_id"] in rows[fact_id]["linked_claim_ids"]
                assert rows[fact_id]["text"]

    # And nothing beyond the union. The whole canonical fact pool is not what
    # this read is: `omitted_facts` spans every canonical fact minus the
    # selected ones, and handing that to a browser would be the general
    # Knowledge manager the product spec excludes.
    linked_ids = {
        fact_id
        for claim in [
            draft["source"]["headline"],
            *draft["source"]["contacts"],
            *(claim for section in draft["source"]["sections"] for claim in section["claims"]),
        ]
        for fact_id in claim["fact_ids"]
    }
    candidate_ids = {
        candidate["fact_id"] for candidate in draft["source"]["selection"]["candidates"]
    }
    assert set(rows) == linked_ids | candidate_ids


def test_the_preview_is_the_rendered_draft_and_is_safe_to_frame(api_worker) -> None:
    """architecture §13: server-rendered HTML for an isolated iframe.

    The headers are the assertion, not decoration. The document is framed with
    `sandbox` by the client, but a preview that depended on the client
    remembering to would be one forgotten attribute away from running whatever
    the response contained.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Preview Co")
    read = _read(api_worker, working_draft_id)

    response = api_worker.client.get(f"{API_PREFIX}/working-drafts/{working_draft_id}/preview")

    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "style-src 'unsafe-inline'" in response.headers["Content-Security-Policy"]
    # The version is named, so a client can tell which edit it framed.
    assert response.headers["ETag"] == read.headers["ETag"]
    assert "<script" not in response.text
    first_claim = read.json()["outline"]["sections"][0]["claims"][0]["text"]
    assert first_claim.split()[0] in response.text


def test_removing_a_pending_claim_is_the_resolution_no_other_command_reaches(
    api_worker,
) -> None:
    """product-spec §10: removal is one of the three resolutions for free text.

    The three arms are one item because they are one rule: the patch removes an
    unauthorized claim, refuses one the fact selection authorizes, and refuses
    the structural claims outright.
    """
    application_id, working_draft_id, _sources = _drafted(api_worker, "Removal Co")
    edit = _unsupported_edit(api_worker, application_id)
    pending = _patch(
        api_worker, working_draft_id, _read(api_worker, working_draft_id).headers["ETag"], [edit]
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["pending_claim_ids"] == [edit["claim_id"]]

    read = _read(api_worker, working_draft_id)
    body = read.json()
    authorized = next(
        claim["claim_id"]
        for section in body["outline"]["sections"]
        for claim in section["claims"]
        if claim["claim_type"] != "pending" and claim["fact_ids"]
    )

    refused = _remove(api_worker, working_draft_id, read.headers["ETag"], [authorized])
    assert refused.status_code == 412, refused.text
    assert "apply_selection_change" in refused.json()["detail"]

    structural = _remove(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [body["outline"]["headline"]["claim_id"]],
    )
    assert structural.status_code == 412, structural.text
    assert "structural" in structural.json()["detail"]

    removed = _remove(api_worker, working_draft_id, read.headers["ETag"], [edit["claim_id"]])

    assert removed.status_code == 200, removed.text
    after = _read(api_worker, working_draft_id).json()
    assert edit["claim_id"] not in {
        claim["claim_id"] for section in after["outline"]["sections"] for claim in section["claims"]
    }
    # The two refusals above changed nothing, so this is the only version bump.
    assert after["edit_version"] == body["edit_version"] + 1
    # A section left empty keeps its heading: removing a line is not permission
    # to restructure the document.
    assert [section["name"] for section in after["outline"]["sections"]] == [
        section["name"] for section in body["outline"]["sections"]
    ]


def test_a_patch_that_says_nothing_or_contradicts_itself_is_refused(api_worker) -> None:
    """`422`, before anything is applied. An empty patch is not a save."""
    application_id, working_draft_id, _sources = _drafted(api_worker, "Empty Patch Co")
    etag = _read(api_worker, working_draft_id).headers["ETag"]
    edit = _unsupported_edit(api_worker, application_id)

    empty = api_worker.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_edits": [], "claim_removals": []},
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )
    assert empty.status_code == 422, empty.text

    contradictory = api_worker.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_edits": [edit], "claim_removals": [edit["claim_id"]]},
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )
    assert contradictory.status_code == 422, contradictory.text
    assert _read(api_worker, working_draft_id).headers["ETag"] == etag


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


def test_validation_run_read_remains_historical_after_the_draft_moves(api_worker) -> None:
    application_id, working_draft_id, _sources = _drafted(api_worker, "Historical Run Co")
    validated = _validated(api_worker, working_draft_id)

    read = _read(api_worker, working_draft_id)
    claim = working_claim(api_worker.services, application_id, "sales.metric.performance")
    moved = _patch(
        api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}],
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["edit_version"] > validated["edit_version"]

    historical = api_worker.client.get(
        f"{API_PREFIX}/validation-runs/{validated['validation_run_id']}"
    )
    assert historical.status_code == 200, historical.text
    historical_body = historical.json()
    assert historical_body.pop("created_at")
    assert historical_body == validated
    assert historical_body["edit_version"] < moved.json()["edit_version"]


def test_validation_run_http_projection_preserves_unknown_groups_and_issue_codes(
    api_worker,
) -> None:
    application_id, working_draft_id, _sources = _drafted(
        api_worker, "Forward Compatible Report Co"
    )
    ordinary = _validated(api_worker, working_draft_id)
    lineage = api_worker.services.repository.validation_lineage(ordinary["validation_run_id"])
    report = ValidationReport(
        passed=False,
        groups={"content": True, "future-validator-group": False},
        issues=[
            ValidationIssue(
                group="future-validator-group",
                code="future-issue-code",
                message="A validator added later supplied this issue.",
                hard=False,
            )
        ],
        evidence={"future-evidence": {"kept": [1, "two", False]}},
    )
    run_id = api_worker.services.repository.record_validation(
        application_id,
        "pre-render",
        report,
        lineage=lineage,
    )

    response = api_worker.client.get(f"{API_PREFIX}/validation-runs/{run_id}")

    assert response.status_code == 200, response.text
    assert response.json()["report"] == api_worker.services.repository.validation_report(
        run_id
    ).model_dump(mode="json")
    assert response.json()["report"]["groups"]["future-validator-group"] is False
    assert response.json()["report"]["issues"] == [
        {
            "group": "future-validator-group",
            "code": "future-issue-code",
            "message": "A validator added later supplied this issue.",
            "hard": False,
        }
    ]
    assert response.json()["report"]["evidence"]["future-evidence"] == {"kept": [1, "two", False]}


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


def test_approval_preserves_a_diverged_working_projection_and_returns_a_specific_code(
    api_worker,
) -> None:
    """An edit outside the Web editor is evidence to preserve, not output to overwrite."""
    application_id, working_draft_id, _sources = _drafted(
        api_worker, "Diverged Projection Co"
    )
    validated = _validated(api_worker, working_draft_id)
    markdown_path = api_worker.services.artifacts.working_paths(application_id).markdown
    edited_projection = markdown_path.read_text(encoding="utf-8") + "\nmanual edit\n"
    markdown_path.write_text(edited_projection, encoding="utf-8")

    response = _post(
        api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": validated["edit_version"],
            "validation_run_id": validated["validation_run_id"],
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "WORKING_PROJECTION_DIVERGED"
    assert markdown_path.read_text(encoding="utf-8") == edited_projection
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
