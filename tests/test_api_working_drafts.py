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
from html.parser import HTMLParser

import pytest
from api_harness import MUTATION_HEADERS, analyze_offline
from helpers import ACCOUNT_MANAGER_JOB, artifact_path, working_claim, working_draft_paths

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import (
    ApplySelectionChangeCommand,
    IngestCommand,
    ValidateDraftCommand,
)
from cv_engine.application.errors import InfrastructureFailure, StateConflict
from cv_engine.domain.contracts.validation import ValidationIssue, ValidationReport
from cv_engine.util import new_id

UNSUPPORTED_WORDING = "Delivered 30% improvement in direct SaaS Sales."


class _VisibleText(HTMLParser):
    """Collect rendered text while ignoring inline safety/presentation tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _visible_html_text(value: str) -> str:
    parser = _VisibleText()
    parser.feed(value)
    return "".join(parser.parts)


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
    return analyze_offline(harness, application_id, ACCOUNT_MANAGER_JOB)


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


def _add(harness, working_draft_id: str, etag: str, claim_additions: list[dict]):
    return harness.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_additions": claim_additions},
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )


def _reorder(harness, working_draft_id: str, etag: str, body: dict):
    return harness.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json=body,
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )


def _state(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _snapshots(harness, application_id: str) -> list[dict]:
    """Every historical draft snapshot registered for this Application."""
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}/artifacts")
    assert response.status_code == 200, response.text
    return [
        item
        for item in response.json()["items"]
        if item["artifact_type"] == "working_draft_snapshot"
    ]


def _audit(
    transaction_manager, application_projection_reader, application_id: str, action: str
) -> dict:
    """The one audit record for this action, or an assertion naming what is there."""
    with transaction_manager.read() as tx:
        records = [
            record
            for record in application_projection_reader.audit_records(tx, application_id)
            if record["action"] == action
        ]
    assert len(records) == 1, records
    return records[0]


def _unsupported_edit(harness, application_id: str) -> dict:
    """One claim rewritten into wording no fact authorizes."""
    claim = working_claim(harness.services, application_id, "sales.metric.performance")
    return {"claim_id": claim.claim_id, "fact_ids": [], "text": UNSUPPORTED_WORDING}


# --- E1: generation ----------------------------------------------------------


def test_generation_reopens_the_exact_parent_revision_only_for_its_own_application(
    ai_api_worker,
    monkeypatch,
    transaction_manager,
    application_projection_reader,
) -> None:
    """A parent revision is reopened as approved, never recomposed, and never lent.

    Another Application naming it is refused as broken lineage and gets no
    draft; its owner gets the approved content back exactly, without the plan
    being consulted again.
    """
    application_id, working_draft_id, sources = _drafted(ai_api_worker, "Parent Revision Co")
    original = _read(ai_api_worker, working_draft_id).json()
    validated = _validated(ai_api_worker, working_draft_id)
    approved = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": validated["edit_version"],
            "validation_run_id": validated["validation_run_id"],
        },
    )
    assert approved.status_code == 201, approved.text
    revision_id = approved.json()["revision_id"]

    intruder_id = _application(ai_api_worker.services, "Parent Intruder Co")
    intruder_sources = _analyze(ai_api_worker, intruder_id)
    borrowed = _post(
        ai_api_worker,
        f"/applications/{intruder_id}/working-draft/generate",
        {
            "job_analysis_id": intruder_sources["job_analysis"],
            "selection_plan_id": intruder_sources["selection_plan"],
            "parent_revision_id": revision_id,
        },
    )
    assert borrowed.status_code == 412, borrowed.text
    assert borrowed.json()["code"] == "LINEAGE_BROKEN"
    with transaction_manager.read() as tx:
        approved_revision = application_projection_reader.approved_revision(tx, revision_id)
    assert approved_revision.application_id == application_id
    assert _state(ai_api_worker, intruder_id)["active_working_draft_id"] is None

    def refuse_recomposition(**_kwargs):
        raise AssertionError("reopening approved content must not recompose it from the plan")

    monkeypatch.setattr(ai_api_worker.services.drafts, "_compose", refuse_recomposition)

    queued = _post(
        ai_api_worker,
        f"/applications/{application_id}/working-draft/generate",
        {
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            "parent_revision_id": revision_id,
        },
    )
    assert queued.status_code == 202, queued.text
    finished = ai_api_worker.wait_for_operation(queued.json()["id"])
    assert finished["status"] == "succeeded", finished
    draft_id = next(
        output["output_id"]
        for output in finished["outputs"]
        if output["output_type"] == "working_draft"
    )
    reopened = _read(ai_api_worker, draft_id).json()
    assert reopened["parent_revision_id"] == revision_id
    assert reopened["outline"] == original["outline"]


# --- E2: read, ETag, and optimistic update -----------------------------------


def test_a_save_carrying_a_stale_etag_is_a_conflict_that_changes_nothing(ai_api_worker) -> None:
    """The concurrency matrix's first two rows: two autosaves, and a second writer.

    A second save with the same ETag is refused, and so is a Web autosave whose
    ETag an out-of-band edit made stale - every writer shares one optimistic
    draft version, not a store of its own. The edit goes through the draft
    service directly, the way a maintenance path or a second Web session
    reaches it. The assertion that matters is that nothing moved: a `409` that
    had already written would be worse than no check at all, because the
    client would be told its save failed while the document moved underneath
    it.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Same Etag Co")
    read = _read(ai_api_worker, working_draft_id)
    claim = working_claim(ai_api_worker.services, application_id, "sales.metric.performance")
    edits = [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}]
    first = _patch(ai_api_worker, working_draft_id, read.headers["ETag"], edits)
    assert first.status_code == 200, first.text

    second = _patch(ai_api_worker, working_draft_id, read.headers["ETag"], edits)

    assert second.status_code == 409, second.text
    assert second.json()["code"] == "STATE_CONFLICT"
    after = _read(ai_api_worker, working_draft_id).json()
    assert after["edit_version"] == first.json()["edit_version"]
    assert after["content_hash"] == first.json()["content_hash"]

    fresh = _read(ai_api_worker, working_draft_id)
    ai_api_worker.services.drafts.edit_claim(
        application_id,
        claim.claim_id,
        [claim.fact_ids[0]],
        text=claim.text,
    )
    out_of_band = _read(ai_api_worker, working_draft_id).json()
    assert out_of_band["edit_version"] == fresh.json()["edit_version"] + 1

    stale_web = _patch(ai_api_worker, working_draft_id, fresh.headers["ETag"], edits)
    assert stale_web.status_code == 409, stale_web.text
    assert stale_web.json()["code"] == "STATE_CONFLICT"
    after = _read(ai_api_worker, working_draft_id).json()
    assert (after["edit_version"], after["content_hash"]) == (
        out_of_band["edit_version"],
        out_of_band["content_hash"],
    )


def test_unauthorized_free_text_is_kept_pending_and_removal_is_its_own_resolution(
    ai_api_worker,
) -> None:
    """§14 and product-spec §10: free text is saved pending, and removal resolves it.

    Unauthorized free text is saved, not discarded and not refused. Removal is
    one of the three resolutions for it, and its three arms are one rule: the
    patch removes an unauthorized claim, refuses one the fact selection
    authorizes, and refuses the structural claims outright.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Removal Co")
    edit = _unsupported_edit(ai_api_worker, application_id)
    pending = _patch(
        ai_api_worker,
        working_draft_id,
        _read(ai_api_worker, working_draft_id).headers["ETag"],
        [edit],
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["pending_claim_ids"] == [edit["claim_id"]]

    read = _read(ai_api_worker, working_draft_id)
    body = read.json()
    saved = next(
        claim
        for section in body["source"]["sections"]
        for claim in section["claims"]
        if claim["claim_id"] == edit["claim_id"]
    )
    assert saved["claim_type"] == "pending"
    assert saved["text"] == UNSUPPORTED_WORDING
    assert saved["pending_reason"]

    authorized = next(
        claim["claim_id"]
        for section in body["outline"]["sections"]
        for claim in section["claims"]
        if claim["claim_type"] != "pending" and claim["fact_ids"]
    )

    refused = _remove(ai_api_worker, working_draft_id, read.headers["ETag"], [authorized])
    assert refused.status_code == 412, refused.text
    assert "apply_selection_change" in refused.json()["detail"]

    structural = _remove(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [body["outline"]["headline"]["claim_id"]],
    )
    assert structural.status_code == 412, structural.text
    assert "structural" in structural.json()["detail"]

    removed = _remove(ai_api_worker, working_draft_id, read.headers["ETag"], [edit["claim_id"]])

    assert removed.status_code == 200, removed.text
    after = _read(ai_api_worker, working_draft_id).json()
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


def test_a_manually_added_line_lands_pending_and_is_removable(ai_api_worker) -> None:
    """A free-hand line the user writes has no fact behind it, so it follows the
    same pending resolution as free text an edit could not authorize - and the
    same removal is what a person takes back with. A line for a section the
    draft does not have is refused and changes nothing.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Manual Line Co")
    read = _read(ai_api_worker, working_draft_id)

    unknown = _add(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"section": "לא קיים", "text": "טקסט כלשהו"}],
    )
    assert unknown.status_code == 404, unknown.text
    assert _read(ai_api_worker, working_draft_id).headers["ETag"] == read.headers["ETag"]

    section_name = read.json()["outline"]["sections"][0]["name"]
    new_text = "שורה שנכתבה ידנית ואינה מבוססת על עובדה קיימת."

    response = _add(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"section": section_name, "text": new_text}],
    )

    assert response.status_code == 200, response.text
    after = _read(ai_api_worker, working_draft_id).json()
    section = next(
        section for section in after["outline"]["sections"] if section["name"] == section_name
    )
    added = next(claim for claim in section["claims"] if claim["text"] == new_text)
    assert added["claim_type"] == "pending"
    assert added["fact_ids"] == []
    assert added["pending_reason"]
    assert added["claim_id"] in response.json()["pending_claim_ids"]

    removed = _remove(
        ai_api_worker,
        working_draft_id,
        _read(ai_api_worker, working_draft_id).headers["ETag"],
        [added["claim_id"]],
    )
    assert removed.status_code == 200, removed.text
    final = _read(ai_api_worker, working_draft_id).json()
    assert added["claim_id"] not in {
        claim["claim_id"] for section in final["outline"]["sections"] for claim in section["claims"]
    }


# --- M4 Stage D: the editor's read, its preview, and claim removal -----------


def test_the_draft_read_carries_an_outline_the_editor_can_address(ai_api_worker) -> None:
    """The outline is derived from the same document `source` carries.

    Asserted against `source` rather than against a fixture, because the claim
    that matters is that the two cannot disagree: the outline is computed per
    read from that object, not stored beside it.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Outline Co")
    body = _read(ai_api_worker, working_draft_id).json()
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


def test_the_facts_read_is_the_union_of_linked_facts_and_plan_candidates(ai_api_worker) -> None:
    """Neither set covers the other, which is the whole reason for this read.

    Contacts come from the candidate context and appear in no SelectionPlan; an
    omitted candidate appears in no claim. A read that returned only one of them
    would leave the editor unable to say either what backs a line or what could
    be added to one.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Fact Union Co")
    draft = _read(ai_api_worker, working_draft_id).json()
    response = ai_api_worker.client.get(f"{API_PREFIX}/working-drafts/{working_draft_id}/facts")

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


def test_the_preview_is_the_rendered_draft_and_is_safe_to_frame(ai_api_worker) -> None:
    """architecture §13: server-rendered HTML for an isolated iframe.

    The headers are the assertion, not decoration. The document is framed with
    `sandbox` by the client, but a preview that depended on the client
    remembering to would be one forgotten attribute away from running whatever
    the response contained.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Preview Co")
    read = _read(ai_api_worker, working_draft_id)

    response = ai_api_worker.client.get(f"{API_PREFIX}/working-drafts/{working_draft_id}/preview")

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


def test_a_patch_that_says_nothing_or_contradicts_itself_is_refused(ai_api_worker) -> None:
    """`422`, before anything is applied. An empty patch is not a save."""
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Empty Patch Co")
    etag = _read(ai_api_worker, working_draft_id).headers["ETag"]
    edit = _unsupported_edit(ai_api_worker, application_id)

    empty = ai_api_worker.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_edits": [], "claim_removals": []},
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )
    assert empty.status_code == 422, empty.text

    contradictory = ai_api_worker.client.patch(
        f"{API_PREFIX}/working-drafts/{working_draft_id}",
        json={"claim_edits": [edit], "claim_removals": [edit["claim_id"]]},
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )
    assert contradictory.status_code == 422, contradictory.text
    assert _read(ai_api_worker, working_draft_id).headers["ETag"] == etag


def test_reorder_preserves_section_membership_and_survives_a_fresh_read(ai_api_worker) -> None:
    _application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Reorder Co")
    before = _read(ai_api_worker, working_draft_id)
    sections = before.json()["outline"]["sections"]
    assert len(sections) >= 2
    target = next(section for section in sections if len(section["claims"]) >= 2)
    section_order = [section["name"] for section in reversed(sections)]
    claim_order = [claim["claim_id"] for claim in reversed(target["claims"])]

    changed = _reorder(
        ai_api_worker,
        working_draft_id,
        before.headers["ETag"],
        {"section_order": section_order, "claim_orders": {target["name"]: claim_order}},
    )

    assert changed.status_code == 200, changed.text
    after = _read(ai_api_worker, working_draft_id)
    assert [section["name"] for section in after.json()["outline"]["sections"]] == section_order
    reordered = next(
        section
        for section in after.json()["outline"]["sections"]
        if section["name"] == target["name"]
    )
    assert [claim["claim_id"] for claim in reordered["claims"]] == claim_order
    assert after.json()["edit_version"] == before.json()["edit_version"] + 1
    preview = ai_api_worker.client.get(f"{API_PREFIX}/working-drafts/{working_draft_id}/preview")
    assert preview.status_code == 200, preview.text
    ordered_text = [claim["text"] for claim in reordered["claims"]]
    preview_text = _visible_html_text(preview.text)
    assert [preview_text.index(text) for text in ordered_text] == sorted(
        preview_text.index(text) for text in ordered_text
    )

    invalid = _reorder(
        ai_api_worker,
        working_draft_id,
        after.headers["ETag"],
        {"claim_orders": {target["name"]: claim_order[:-1]}},
    )
    assert invalid.status_code == 412, invalid.text
    assert _read(ai_api_worker, working_draft_id).headers["ETag"] == after.headers["ETag"]


# --- E3: selection change, archive, replace ----------------------------------


def test_a_selection_change_creates_a_plan_and_moves_the_draft_onto_it(ai_api_worker) -> None:
    """§14: one immutable SelectionPlan, and the draft rebuilt from it."""
    application_id, working_draft_id, sources = _drafted(ai_api_worker, "Reselection Co")
    before = _read(ai_api_worker, working_draft_id).json()
    # A Core Skills fact that the engine selected: excluding one of those does
    # not cost a role block its floor or empty a required tag, which are the
    # two exclusions the domain refuses outright.
    excluded = next(
        candidate["fact_id"]
        for candidate in before["source"]["selection"]["candidates"]
        if candidate["section"] == "Core Skills" and candidate["outcome"] == "selected"
    )

    response = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/apply-selection-change",
        {"expected_edit_version": before["edit_version"], "excluded_fact_ids": [excluded]},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["selection_plan_id"] != sources["selection_plan"]
    assert body["edit_version"] == before["edit_version"] + 1
    after = _read(ai_api_worker, working_draft_id).json()
    assert after["selection_plan_id"] == body["selection_plan_id"]
    assert excluded not in after["source"]["selected_fact_ids"]
    assert after["source"]["omitted_facts"][excluded] == "excluded_by_user"


def test_selection_change_rolls_back_plan_and_draft_when_the_draft_write_fails(
    ai_api_worker,
    monkeypatch,
    transaction_manager,
    application_projection_reader,
) -> None:
    from cv_engine.infrastructure.persistence.selection_drafts import SqlAlchemySelectionDraftStore

    application_id, working_draft_id, sources = _drafted(ai_api_worker, "Reselection Rollback Co")
    before = _read(ai_api_worker, working_draft_id).json()
    services = ai_api_worker.services
    markdown_path = working_draft_paths(services, application_id).markdown
    markdown = markdown_path.read_text(encoding="utf-8")
    original = SqlAlchemySelectionDraftStore.update_selection

    def fail_after_update(*args, **kwargs):
        original(*args, **kwargs)
        raise InfrastructureFailure("draft write rollback")

    monkeypatch.setattr(SqlAlchemySelectionDraftStore, "update_selection", fail_after_update)
    with pytest.raises(InfrastructureFailure, match="draft write rollback"):
        services.drafts.apply_selection_change(
            ApplySelectionChangeCommand(
                working_draft_id=working_draft_id,
                expected_edit_version=before["edit_version"],
            ),
            analysis_service=services.analysis,
        )
    assert _read(ai_api_worker, working_draft_id).json() == before
    with transaction_manager.read() as tx:
        assert (
            application_projection_reader.latest_selection_plan(tx, application_id).id
            == sources["selection_plan"]
        )
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_a_selection_change_refuses_a_draft_carrying_manual_wording(ai_api_worker) -> None:
    """§14's other branch: a deterministic rebuild would discard the user's text."""
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Manual Wording Co")
    read = _read(ai_api_worker, working_draft_id)
    edited = _patch(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [_unsupported_edit(ai_api_worker, application_id)],
    )
    assert edited.status_code == 200, edited.text

    response = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/apply-selection-change",
        {"expected_edit_version": edited.json()["edit_version"], "excluded_fact_ids": []},
    )

    assert response.status_code == 412, response.text
    assert "regenerate_section" in response.json()["detail"]
    after = _read(ai_api_worker, working_draft_id).json()
    assert after["edit_version"] == edited.json()["edit_version"]


def test_keep_and_archive_register_the_snapshot_before_the_draft_moves(
    ai_api_worker,
    transaction_manager,
    application_projection_reader,
) -> None:
    """§14: the historical record exists first, and the payload is really there.

    Replacement with Keep materializes the snapshot and replaces the draft in
    place; archiving that draft registers its own snapshot before clearing the
    active pointer.
    """
    application_id, working_draft_id, sources = _drafted(ai_api_worker, "Replace Keep Co")
    before = _read(ai_api_worker, working_draft_id).json()

    response = _post(
        ai_api_worker,
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
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    replaced = _read(ai_api_worker, working_draft_id).json()
    assert replaced["edit_version"] == before["edit_version"] + 1
    assert replaced["active"] is True
    assert [
        item["metadata"]["edit_version"] for item in _snapshots(ai_api_worker, application_id)
    ] == [before["edit_version"]]
    assert (
        _audit(
            transaction_manager,
            application_projection_reader,
            application_id,
            "replace_working_draft",
        )["client"]
        == "web"
    )

    archived = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/archive",
        {"expected_edit_version": replaced["edit_version"]},
    )

    assert archived.status_code == 200, archived.text
    body = archived.json()
    artifacts = ai_api_worker.client.get(f"{API_PREFIX}/applications/{application_id}/artifacts")
    registered = next(
        item for item in artifacts.json()["items"] if item["id"] == body["artifact_version_id"]
    )
    assert registered["artifact_type"] == "working_draft_snapshot"
    assert registered["lifecycle_status"] == "archived"
    assert registered["metadata"]["working_draft_id"] == working_draft_id
    assert (
        _audit(
            transaction_manager,
            application_projection_reader,
            application_id,
            "archive_working_draft",
        )["client"]
        == "web"
    )
    with transaction_manager.read() as tx:
        artifact_version = application_projection_reader.artifact_version(
            tx, body["artifact_version_id"]
        )
    stored = artifact_path(ai_api_worker.services, artifact_version["path"])
    assert json.loads(stored.read_text(encoding="utf-8"))["application_id"] == application_id
    state = _state(ai_api_worker, application_id)
    assert state["active_working_draft_id"] is None
    assert state["working_draft_state"] == "none"


def test_a_refused_replacement_leaves_the_existing_draft_exactly_as_it_was(ai_api_worker) -> None:
    """§14: nothing is deleted or deactivated before the replacement succeeds."""
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Replace Refusal Co")
    other_id = _application(ai_api_worker.services, "Replace Refusal Other Co")
    other_sources = _analyze(ai_api_worker, other_id)
    before = _read(ai_api_worker, working_draft_id).json()

    response = _post(
        ai_api_worker,
        f"/applications/{application_id}/working-draft/replace",
        {
            "working_draft_id": working_draft_id,
            "expected_edit_version": before["edit_version"],
            "job_analysis_id": other_sources["job_analysis"],
            "selection_plan_id": other_sources["selection_plan"],
        },
    )

    assert response.status_code == 412, response.text
    assert _read(ai_api_worker, working_draft_id).json() == before
    assert _state(ai_api_worker, application_id)["active_working_draft_id"] == working_draft_id


# --- E3a: the window between the `202` and the write -------------------------
#
# Replacement is accepted as an Operation, so the command and the write are separated by
# however long the queue is. `expected_edit_version` proved the draft was untouched when
# the command was admitted and nothing re-checked it afterwards, so an edit or an archive
# landing in that window was not seen: the edit was overwritten, and the archive turned
# "replace this draft" into "create a new one". These drive that window directly by
# holding the Operation queued while the draft moves underneath it.


def _queued_replacement(harness, application_id: str, working_draft_id: str, sources, **extra):
    """Submit a replacement without letting anything execute it yet."""
    before = _read(harness, working_draft_id).json()
    response = _post(
        harness,
        f"/applications/{application_id}/working-draft/replace",
        {
            "working_draft_id": working_draft_id,
            "expected_edit_version": before["edit_version"],
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            **extra,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["id"], before


def test_a_draft_that_moves_after_the_replacement_was_accepted_is_not_overwritten(
    ai_api_paused,
) -> None:
    """§14: the version is re-checked at activation, not only at admission.

    An edit landing in the window is not overwritten. An archive landing in it
    does not turn "replace this draft" into "create a new one": the command
    named one draft, so it may not land on a different record. The old write
    selected by `application_id + active`, so an archived draft left no active
    row and the replacement inserted a brand new draft with a new id - a record
    nobody asked for, presented as the replacement of one that had been set
    aside.
    """
    application_id, working_draft_id, sources = _drafted(ai_api_paused, "Replace Race Co")
    operation_id, before = _queued_replacement(
        ai_api_paused, application_id, working_draft_id, sources
    )

    read = _read(ai_api_paused, working_draft_id)
    edited = _patch(
        ai_api_paused,
        working_draft_id,
        read.headers["ETag"],
        [_unsupported_edit(ai_api_paused, application_id)],
    )
    assert edited.status_code == 200, edited.text

    finished = ai_api_paused.run_operation(operation_id)

    assert finished["status"] == "failed", finished
    assert finished["failure_code"] == "SOURCE_CHANGED"
    after = _read(ai_api_paused, working_draft_id).json()
    assert after["edit_version"] == before["edit_version"] + 1
    assert after["content_hash"] == edited.json()["content_hash"]

    operation_id, before = _queued_replacement(
        ai_api_paused, application_id, working_draft_id, sources
    )
    archived = _post(
        ai_api_paused,
        f"/working-drafts/{working_draft_id}/archive",
        {"expected_edit_version": before["edit_version"]},
    )
    assert archived.status_code == 200, archived.text

    finished = ai_api_paused.run_operation(operation_id)

    assert finished["status"] == "failed", finished
    assert finished["failure_code"] == "SOURCE_CHANGED"
    state = _state(ai_api_paused, application_id)
    assert state["active_working_draft_id"] is None
    assert state["working_draft_state"] == "none"


def test_a_replacement_key_settles_replays_and_refuses_a_different_replacement(
    ai_api_paused,
    transaction_manager,
    application_projection_reader,
) -> None:
    """§14 and §7 "same key, different payload": the key decides, first.

    Keep is a side effect, so a replay must not reach it at all. Keep ran ahead
    of the idempotency check, so a resend did the work again before being
    recognized as a replay; what that produced depended on the store rather than
    on the command, which is why the assertion is that the replay is settled
    first, not that some particular second failure occurs.

    A replay is answered from the reservation, not by re-checking
    preconditions. The first replacement is what moves the draft, so by the time
    a client resends the version it names is no longer current; re-deriving
    the command would fail that resend on the state its own first attempt
    produced.

    Two different replacements are two commands, whatever key they carry. The
    draft identity travels in the Operation payload, which is what the
    idempotency check hashes, so a changed Keep decision cannot be served back
    as a replay.
    """
    application_id, working_draft_id, sources = _drafted(ai_api_paused, "Replace Replay Co")
    before = _read(ai_api_paused, working_draft_id).json()
    body = {
        "working_draft_id": working_draft_id,
        "expected_edit_version": before["edit_version"],
        "job_analysis_id": sources["job_analysis"],
        "selection_plan_id": sources["selection_plan"],
        "keep_previous": True,
    }
    path = f"/applications/{application_id}/working-draft/replace"
    key = {"Idempotency-Key": "replace-replay-1"}

    first = _post(ai_api_paused, path, body, **key)
    second = _post(ai_api_paused, path, body, **key)

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    operation_id = first.json()["id"]
    assert second.json()["id"] == operation_id
    assert [
        item["metadata"]["edit_version"] for item in _snapshots(ai_api_paused, application_id)
    ] == [before["edit_version"]]
    # `_audit` asserts there is exactly one record for the action, which is the assertion
    # that matters here: a second Keep would write a second audit record beside the second
    # snapshot. `details_json` is canonical JSON text rather than a mapping.
    kept = json.loads(
        _audit(
            transaction_manager,
            application_projection_reader,
            application_id,
            "replace_working_draft",
        )["details_json"]
    )
    assert kept["kept"] is True
    assert kept["edit_version"] == before["edit_version"]

    assert ai_api_paused.run_operation(operation_id)["status"] == "succeeded"
    after = _read(ai_api_paused, working_draft_id).json()
    assert after["edit_version"] == before["edit_version"] + 1

    replayed = _post(ai_api_paused, path, body, **key)

    assert replayed.status_code == 202, replayed.text
    assert replayed.json()["id"] == operation_id
    # And the replacement ran once: the draft is not replaced again.
    assert _read(ai_api_paused, working_draft_id).json()["edit_version"] == after["edit_version"]

    reused = _post(ai_api_paused, path, {**body, "keep_previous": False}, **key)

    assert reused.status_code == 409, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_a_replacement_interrupted_after_keep_resumes_without_a_second_snapshot(
    ai_api_paused,
    transaction_manager,
    application_projection_reader,
) -> None:
    """§14: the crash window between Keep and the Operation is recoverable.

    Keep runs under a claimed receipt and before the Operation exists, which is what keeps
    a worker from replacing the draft ahead of its own historical copy. The cost is a gap:
    a crash there leaves a pending receipt, a written snapshot, and no Operation. Re-taking
    Keep would fail on the immutable path already written and stick the command forever,
    so it is an ensure - the existing snapshot for this exact draft, version, and hash is
    recognized as the success it is, and the resend goes on to create the Operation.

    The interruption is simulated at the service boundary rather than by killing a process:
    the first call is driven through the application layer with Operation creation made to
    fail, which leaves exactly the state a crash would.
    """
    application_id, working_draft_id, sources = _drafted(ai_api_paused, "Replace Interrupted Co")
    before = _read(ai_api_paused, working_draft_id).json()
    body = {
        "working_draft_id": working_draft_id,
        "expected_edit_version": before["edit_version"],
        "job_analysis_id": sources["job_analysis"],
        "selection_plan_id": sources["selection_plan"],
        "keep_previous": True,
    }
    path = f"/applications/{application_id}/working-draft/replace"
    key = {"Idempotency-Key": "replace-interrupted-1"}

    operations = ai_api_paused.services.operation_submissions
    original = operations.submit_draft

    def fail_after_keep(*_args, **_kwargs):
        raise InfrastructureFailure("interrupted before the Operation was created")

    operations.submit_draft = fail_after_keep
    try:
        interrupted = _post(ai_api_paused, path, body, **key)
    finally:
        operations.submit_draft = original
    assert interrupted.status_code == 500, interrupted.text

    # The state a crash would leave: the snapshot is written, and nothing is queued.
    snapshots = _snapshots(ai_api_paused, application_id)
    assert [item["metadata"]["edit_version"] for item in snapshots] == [before["edit_version"]]

    resumed = _post(ai_api_paused, path, body, **key)

    assert resumed.status_code == 202, resumed.text
    assert ai_api_paused.run_operation(resumed.json()["id"])["status"] == "succeeded"
    # One snapshot, and one audit record: Keep was ensured, not repeated.
    assert [
        item["metadata"]["edit_version"] for item in _snapshots(ai_api_paused, application_id)
    ] == [before["edit_version"]]
    _audit(
        transaction_manager, application_projection_reader, application_id, "replace_working_draft"
    )
    assert (
        _read(ai_api_paused, working_draft_id).json()["edit_version"] == before["edit_version"] + 1
    )


def test_a_registered_snapshot_whose_payload_is_gone_refuses_the_replacement(
    ai_api_paused,
    transaction_manager,
    application_projection_reader,
) -> None:
    """§14: a registration is not evidence that the historical copy still exists.

    The ensure that makes a crash recoverable reads a row, and a row says a snapshot was
    written once - not that its payload is still there or still says what it said. Taken as
    proof, a snapshot that has been moved, deleted, or altered would let the replacement
    overwrite the active draft against a copy that cannot be trusted, which is precisely
    the wording the Keep decision existed to preserve. So the payload is verified, and
    anything but `ok` refuses.
    """
    application_id, working_draft_id, sources = _drafted(ai_api_paused, "Replace Lost Snapshot Co")
    before = _read(ai_api_paused, working_draft_id).json()
    body = {
        "working_draft_id": working_draft_id,
        "expected_edit_version": before["edit_version"],
        "job_analysis_id": sources["job_analysis"],
        "selection_plan_id": sources["selection_plan"],
        "keep_previous": True,
    }
    path = f"/applications/{application_id}/working-draft/replace"
    key = {"Idempotency-Key": "replace-lost-snapshot-1"}

    operations = ai_api_paused.services.operation_submissions
    original = operations.submit_draft

    def fail_after_keep(*_args, **_kwargs):
        raise InfrastructureFailure("interrupted before the Operation was created")

    operations.submit_draft = fail_after_keep
    try:
        assert _post(ai_api_paused, path, body, **key).status_code == 500
    finally:
        operations.submit_draft = original

    # The snapshot is registered, and then its payload is corrupted underneath the row.
    snapshot = _snapshots(ai_api_paused, application_id)[0]
    with transaction_manager.read() as tx:
        stored = application_projection_reader.artifact_version(tx, snapshot["id"])
    artifact_path(ai_api_paused.services, stored["path"]).write_text("tampered", encoding="utf-8")

    refused = _post(ai_api_paused, path, body, **key)

    assert refused.status_code == 409, refused.text
    # And the draft is untouched: no Operation was queued to replace it.
    assert _read(ai_api_paused, working_draft_id).json() == before
    assert _state(ai_api_paused, application_id)["active_working_draft_id"] == working_draft_id


# --- E4: validation ----------------------------------------------------------


def test_a_failed_validation_is_a_successful_outcome_with_its_run_recorded(
    ai_api_worker,
    transaction_manager,
    validation_store,
) -> None:
    """§22: `passed=false` is `200`, and the immutable run is written anyway."""
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Failing Validation Co")
    read = _read(ai_api_worker, working_draft_id)
    edited = _patch(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [_unsupported_edit(ai_api_worker, application_id)],
    )

    response = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": edited.json()["edit_version"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is False
    assert any(issue["code"] == "pending-claim" for issue in body["report"]["issues"])
    with transaction_manager.read() as tx:
        assert validation_store.validation_report(tx, body["validation_run_id"]).passed is (False)
    assert _state(ai_api_worker, application_id)["working_draft_state"] == "validation_failed"
    stale = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": body["edit_version"] + 1},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "STATE_CONFLICT"


def test_a_validation_run_read_is_historical_and_forward_compatible(
    ai_api_worker,
    transaction_manager,
    validation_store,
) -> None:
    """A run describes the version it validated, in whatever vocabulary it was written.

    A run carrying groups, issue codes and evidence from a validator added later
    is projected as stored rather than dropped - recorded while its lineage is
    still the draft's. The ordinary run's read then stays exactly what was
    validated after the draft moves on.
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Historical Run Co")
    validated = _validated(ai_api_worker, working_draft_id)

    with transaction_manager.read() as tx:
        lineage = validation_store.validation_lineage(tx, validated["validation_run_id"])
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
    with transaction_manager.write() as tx:
        run_id = validation_store.record_validation(
            tx,
            application_id,
            "pre-render",
            report,
            lineage=lineage,
        )

    response = ai_api_worker.client.get(f"{API_PREFIX}/validation-runs/{run_id}")

    assert response.status_code == 200, response.text
    with transaction_manager.read() as tx:
        expected_report = validation_store.validation_report(tx, run_id).model_dump(mode="json")
    assert response.json()["report"] == expected_report
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

    read = _read(ai_api_worker, working_draft_id)
    claim = working_claim(ai_api_worker.services, application_id, "sales.metric.performance")
    moved = _patch(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}],
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["edit_version"] > validated["edit_version"]

    historical = ai_api_worker.client.get(
        f"{API_PREFIX}/validation-runs/{validated['validation_run_id']}"
    )
    assert historical.status_code == 200, historical.text
    historical_body = historical.json()
    assert historical_body.pop("created_at")
    assert historical_body == validated
    assert historical_body["edit_version"] < moved.json()["edit_version"]


def _validated(harness, working_draft_id: str) -> dict:
    read = _read(harness, working_draft_id).json()
    response = _post(
        harness,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": read["edit_version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_approval_needs_a_passing_run_of_the_exact_version_it_approves(
    ai_api_worker,
    transaction_manager,
    application_projection_reader,
    draft_lifecycle_store,
    validation_store,
) -> None:
    """The binding checks that could not fail before, failing.

    Approval used to validate for itself, so the run always described the draft
    in front of it. Here the run is real evidence about one version, and three
    ways it stops describing the draft are refused: the draft changes while
    validation runs (no run is recorded at all), the draft is edited after
    validation (approving would freeze content nothing checked), and the run
    did not pass (the refusal says how many issues blocked it).
    """
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Stale Approval Co")
    validated = _validated(ai_api_worker, working_draft_id)
    services = ai_api_worker.services

    with transaction_manager.read() as tx:
        working = draft_lifecycle_store.active_working_draft(tx, application_id)

    from cv_engine.application.services.drafts import validation as validation_module

    original = validation_module.run_draft_validation

    def edit_while_validation_runs(*args, **kwargs):
        report = original(*args, **kwargs)
        services.drafts._commit_edit(working, working.source)
        return report

    with pytest.MonkeyPatch.context() as scoped:
        scoped.setattr(validation_module, "run_draft_validation", edit_while_validation_runs)
        with pytest.raises(StateConflict):
            services.draft_validation.validate_draft(
                ValidateDraftCommand(
                    working_draft_id=working.id,
                    expected_edit_version=working.edit_version,
                )
            )

    with transaction_manager.read() as tx:
        latest = validation_store.latest_validation_for_working_draft(tx, working.id)
    assert latest["id"] == validated["validation_run_id"]

    read = _read(ai_api_worker, working_draft_id)
    claim = working_claim(services, application_id, "sales.metric.performance")
    edited = _patch(
        ai_api_worker,
        working_draft_id,
        read.headers["ETag"],
        [{"claim_id": claim.claim_id, "fact_ids": claim.fact_ids, "text": claim.text}],
    )
    assert edited.status_code == 200, edited.text

    stale = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": edited.json()["edit_version"],
            "validation_run_id": validated["validation_run_id"],
        },
    )

    assert stale.status_code == 412, stale.text
    assert stale.json()["code"] == "VALIDATION_STALE"
    with transaction_manager.read() as tx:
        assert application_projection_reader.approved_revisions(tx, application_id) == []

    unsupported = _patch(
        ai_api_worker,
        working_draft_id,
        _read(ai_api_worker, working_draft_id).headers["ETag"],
        [_unsupported_edit(ai_api_worker, application_id)],
    )
    assert unsupported.status_code == 200, unsupported.text
    failed = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/validate",
        {"expected_edit_version": unsupported.json()["edit_version"]},
    ).json()
    assert failed["passed"] is False

    blocked = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        {
            "expected_edit_version": failed["edit_version"],
            "validation_run_id": failed["validation_run_id"],
        },
    )

    assert blocked.status_code == 412, blocked.text
    assert blocked.json()["code"] == "VALIDATION_BLOCKED"
    assert blocked.json()["context"]["issue_count"] >= 1


def test_the_same_key_returns_the_same_revision_and_a_changed_payload_is_reuse(
    ai_api_worker,
    transaction_manager,
    application_projection_reader,
) -> None:
    """§15: the payload covers all three arguments plus the content hash."""
    application_id, working_draft_id, _sources = _drafted(ai_api_worker, "Approval Key Co")
    validated = _validated(ai_api_worker, working_draft_id)
    body = {
        "expected_edit_version": validated["edit_version"],
        "validation_run_id": validated["validation_run_id"],
    }

    first = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        body,
        **{"Idempotency-Key": "approve-once"},
    )
    repeated = _post(
        ai_api_worker,
        f"/working-drafts/{working_draft_id}/approve",
        body,
        **{"Idempotency-Key": "approve-once"},
    )

    assert first.status_code == 201, first.text
    assert repeated.json() == first.json()
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.approved_revisions(tx, application_id)) == 1

    for changed in (
        {**body, "expected_edit_version": body["expected_edit_version"] + 1},
        {**body, "validation_run_id": new_id()},
    ):
        refused = _post(
            ai_api_worker,
            f"/working-drafts/{working_draft_id}/approve",
            changed,
            **{"Idempotency-Key": "approve-once"},
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.approved_revisions(tx, application_id)) == 1

    _other_app, other_draft_id, _other = _drafted(ai_api_worker, "Approval Key Other Co")
    other = _validated(ai_api_worker, other_draft_id)
    reused = _post(
        ai_api_worker,
        f"/working-drafts/{other_draft_id}/approve",
        {
            "expected_edit_version": other["edit_version"],
            "validation_run_id": other["validation_run_id"],
        },
        **{"Idempotency-Key": "approve-once"},
    )

    assert reused.status_code == 409, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
