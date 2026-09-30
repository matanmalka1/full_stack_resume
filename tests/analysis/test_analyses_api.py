"""API review decisions and the document selection against existing AI analyses.

§13 requires the first analysis activation to commit its immutable JobAnalysis *and*
the Application's CV document, with the analysis's deterministic selection, in one
transaction. The focused tests here hold that behavior as evidence, and the review
decisions that follow: a meaning change creates a new analysis and leaves the
document where it is; a selection decision changes the document's selection in place.
"""

from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS
from helpers import (
    ACCOUNT_MANAGER_JOB,
    REVIEW_DECISION_JOB,
    analysis_proposal,
    persisted_counts,
    seed_draft,
    seed_existing_analysis,
    stored_document,
)

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import AnalyzeCommand, IngestCommand
from cv_engine.domain.contracts.analysis import Requirement
from cv_engine.infrastructure.persistence.documents import SqlAlchemyDocumentStore


def _application(services, company: str, *, job_text: str = ACCOUNT_MANAGER_JOB) -> str:
    return services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Account Manager",
            job_text=job_text,
            acknowledged_duplicates=True,
            client="web",
        )
    ).application_id


def _existing_analysis(
    harness,
    application_id: str,
    transaction_manager,
    application_projection_reader,
    **analysis_values,
) -> str:
    """Seed an analysis record explicitly; these tests exercise later API decisions."""
    with transaction_manager.read() as tx:
        snapshot_id = application_projection_reader.latest_snapshot(tx, application_id)["id"]
    return seed_existing_analysis(
        harness.services,
        AnalyzeCommand(application_id=application_id, job_snapshot_id=snapshot_id),
        **analysis_values,
    ).analysis_id


def _unmet_requirement(quote: str, requirement_id: str) -> Requirement:
    """One mandatory requirement no canonical fact verifies - a hard gap.

    Stored as the requirement alone. Its gap, the Fit it lowers and its severity
    are derived from it where they are read, so nothing here states them twice.
    """
    return Requirement(
        requirement_id=requirement_id,
        text=quote,
        importance="mandatory",
        coverage="unsupported",
    )


REVIEW_ANALYSIS = {
    "requirements": [
        _unmet_requirement("Sales experience at a SaaS company.", "review-saas-company")
    ],
}


def _state(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _document(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}/document")
    assert response.status_code == 200, response.text
    return response.json()


def _post(harness, path: str, payload: dict):
    return harness.client.post(f"{API_PREFIX}{path}", json=payload, headers=MUTATION_HEADERS)


# --- analysis activation ----------------------------------------------------


def test_post_analysis_uses_ai_operation_and_creates_the_document(
    ai_api_worker, fake_openai, requirement_concepts
) -> None:
    fake_openai.script(
        "propose_analysis",
        analysis_proposal(summary="account management role", keywords=["retention"]),
    )
    application_id = _application(ai_api_worker.services, "AI Operation Co")
    snapshot_id = _state(ai_api_worker, application_id)["active_job_snapshot_id"]
    response = _post(
        ai_api_worker,
        f"/applications/{application_id}/analyses",
        {"job_snapshot_id": snapshot_id},
    )
    assert response.status_code == 202, response.text
    completed = ai_api_worker.wait_for_operation(response.json()["id"])
    assert completed["status"] == "succeeded", completed
    # Each scripted provider call also lands as its own provider_response output,
    # preserved for provenance beside the analysis and the document it created.
    outputs = {item["output_type"]: item["output_id"] for item in completed["outputs"]}
    assert set(outputs) == {"job_analysis", "cv_document", "provider_response"}
    assert all(item["active"] for item in completed["outputs"])
    document = _document(ai_api_worker, application_id)
    assert document["id"] == outputs["cv_document"]
    assert document["analysis_id"] == outputs["job_analysis"]
    assert document["content"] is None


def test_an_analysis_creates_its_document_together_or_not_at_all(
    api_paused, monkeypatch, transaction_manager, application_projection_reader
) -> None:
    """§13: the first analysis and the document it creates, one activation.

    Atomic means atomic: only a failure part-way through shows the two rows arrive
    together, a passing happy path cannot. An analysis with no document would leave
    the Application with nothing to draft and no command to create it.
    """
    application_id = _application(api_paused.services, "Atomic Analysis Co")
    with transaction_manager.read() as tx:
        before = len(application_projection_reader.analyses(tx, application_id))

    def refuse_document(*_args, **_kwargs):
        raise RuntimeError("document insert failed")

    monkeypatch.setattr(SqlAlchemyDocumentStore, "create_document", refuse_document)
    with pytest.raises(RuntimeError):
        _existing_analysis(
            api_paused, application_id, transaction_manager, application_projection_reader
        )
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.analyses(tx, application_id)) == before

    monkeypatch.undo()
    analysis_id = _existing_analysis(
        api_paused, application_id, transaction_manager, application_projection_reader
    )
    state = _state(api_paused, application_id)
    assert state["latest_analysis_id"] == analysis_id
    assert state["document_analysis_id"] == analysis_id
    assert state["preparation_state"] == "ready_to_draft"


# --- POST /analyses/{id}/apply-decisions -------------------------------------


@pytest.mark.parametrize("decision", ["classification", "fact_overlay", "emphasis"])
def test_a_decision_changes_only_what_it_decides(
    api_worker, transaction_manager, application_projection_reader, decision
) -> None:
    """Three branches, one history rule.

    A classification decision is the meaning branch: a new immutable analysis, and
    the document stays on the analysis it was built from until it is rebuilt. A fact
    overlay or an emphasis decision is the selection branch: the document's own
    selection changes in place, on the same analysis. The analysis decided against is
    untouched history in every branch.
    """
    if decision == "classification":
        application_id = _application(
            api_worker.services, "Decided Classification Co", job_text=REVIEW_DECISION_JOB
        )
        analysis_id = _existing_analysis(
            api_worker,
            application_id,
            transaction_manager,
            application_projection_reader,
            **REVIEW_ANALYSIS,
        )
    else:
        application_id = _application(api_worker.services, f"Decided {decision} Co")
        analysis_id = _existing_analysis(
            api_worker, application_id, transaction_manager, application_projection_reader
        )
    with transaction_manager.read() as tx:
        original_analysis = application_projection_reader.analysis(tx, analysis_id)
    original_document = _document(api_worker, application_id)
    removed = None
    if decision == "classification":
        submitted = {"profile_override": "account-manager"}
    elif decision == "fact_overlay":
        removed = next(
            candidate["fact_id"]
            for candidate in original_document["selection"]["candidates"]
            if candidate["section"] == "Core Skills" and candidate["outcome"] == "selected"
        )
        submitted = {"excluded_fact_ids": [removed]}
    else:
        submitted = {"emphasis_override": "new-business"}

    response = _post(
        api_worker,
        f"/analyses/{analysis_id}/apply-decisions",
        {
            "application_id": application_id,
            "expected_analysis_id": analysis_id,
            "expected_document_hash": original_document["document_hash"],
            **submitted,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    creates_analysis = decision == "classification"
    assert body["created_analysis"] is creates_analysis
    assert (body["job_analysis_id"] != analysis_id) is creates_analysis
    assert body["document_id"] == original_document["id"]

    with transaction_manager.read() as tx:
        assert application_projection_reader.analysis(tx, analysis_id) == original_analysis

    state = _state(api_worker, application_id)
    document = _document(api_worker, application_id)
    assert state["latest_analysis_id"] == body["job_analysis_id"]
    assert state["document_hash"] == body["document_hash"] == document["document_hash"]
    assert body["state"]["latest_analysis_id"] == state["latest_analysis_id"]
    assert body["state"]["available_actions"] == state["available_actions"]
    assert body["state"]["recommended_action"] == state["recommended_action"]

    if decision == "classification":
        assert body["analysis"]["user_override"] == {"profile": "account-manager"}
        # The document is pinned to the analysis it was built from (§13 decision 3).
        assert document == original_document
        assert state["document_analysis_id"] == analysis_id
        assert "DOCUMENT_ON_OLDER_ANALYSIS" in {warning["code"] for warning in state["warnings"]}
        # The hard gap is still there and still hard. It is information for the
        # user, not a question they must answer before the document exists.
        assert state["review_reasons"] == []
    elif decision == "fact_overlay":
        assert document["analysis_id"] == analysis_id
        assert removed not in document["selection"]["selected_fact_ids"]
        assert {
            candidate["fact_id"]: candidate["reason"]
            for candidate in document["selection"]["candidates"]
        }[removed] == "excluded_by_user"
    else:
        assert document["selection"]["emphasis"] == "new-business"
        assert document["selection"]["emphasis_override"] == "new-business"
        assert state["application"]["emphasis"] == "new-business"
        seed_draft(api_worker.services, application_id)
        content = stored_document(api_worker.services, application_id).content
        assert content is not None
        assert content.emphasis.value == "new-business"
        assert content.selection is not None
        assert content.selection.emphasis_override is not None


RIVERSIDE_POSTING = (
    "About the job\n"
    "Riverside built an AI-powered platform for content creators.\n\n"
    "Requirements:\n\n"
    "1+ years of sales closing experience in the market at a technology company, "
    "with a track record of top performance (must).\n"
    "Native English speaker (multiple languages are a plus).\n"
)


RIVERSIDE_ANALYSIS = {
    "requirements": [
        _unmet_requirement(
            "1+ years of sales closing experience in the market at a technology company",
            "riverside-tech-sales",
        ),
        _unmet_requirement("Native English speaker", "riverside-native-english"),
    ],
}


def test_the_api_refuses_decisions_it_cannot_act_on_without_writing(
    api_paused, database_engine, transaction_manager, application_projection_reader
) -> None:
    """Every refusal of a decision request, none of which is a 500.

    Both kinds at once: a fact overlay is decided against candidate accounting the
    new analysis has not produced yet, so it stays a second command, and the refusal
    leaves no row anywhere.

    Nothing at all: an empty form would put a decision in the history nobody made.

    A value outside its closed set: refused as a request error before a command is
    built, on both routes that accept a classification override.

    Unnamed or moved sources: a decision names the analysis and the document it was
    made beside, or it would be applied to whatever is current when it arrives. A
    missing document token is a malformed request (412); a token naming a document or
    an analysis that has since moved is the lost race (409), and the refused write
    leaves the replacement analysis the latest.
    """
    application_id = _application(
        api_paused.services, "Refused Decisions Co", job_text=RIVERSIDE_POSTING
    )
    analysis_id = _existing_analysis(
        api_paused,
        application_id,
        transaction_manager,
        application_projection_reader,
        **RIVERSIDE_ANALYSIS,
    )
    decisions_path = f"/analyses/{analysis_id}/apply-decisions"
    named = {
        "application_id": application_id,
        "expected_analysis_id": analysis_id,
        "expected_document_hash": _document(api_paused, application_id)["document_hash"],
    }

    before = persisted_counts(database_engine)
    both = _post(
        api_paused,
        decisions_path,
        {
            **named,
            "profile_override": "account-manager",
            "excluded_fact_ids": ["sales.achievement.retention"],
        },
    )
    assert both.status_code == 412, both.text
    assert both.json()["code"] == "PRECONDITION_FAILED"
    assert "fact overlay" in both.json()["detail"]
    assert persisted_counts(database_engine) == before

    empty = _post(api_paused, decisions_path, named)
    assert empty.status_code == 412, empty.text

    snapshot_id = _state(api_paused, application_id)["active_job_snapshot_id"]
    for path, payload in [
        (decisions_path, {**named, "profile_override": "not-a-profile"}),
        (
            f"/applications/{application_id}/analyses",
            {"job_snapshot_id": snapshot_id, "profile_override": "not-a-profile"},
        ),
    ]:
        refused = _post(api_paused, path, payload)
        assert refused.status_code == 422, (path, refused.text)

    unnamed_document = _post(
        api_paused,
        decisions_path,
        {
            "application_id": application_id,
            "expected_analysis_id": analysis_id,
            "pinned_fact_ids": ["sales.summary.new_business"],
        },
    )
    assert unnamed_document.status_code == 412, unnamed_document.text
    assert "expected_document_hash" in unnamed_document.text

    unnamed_analysis = _post(
        api_paused,
        decisions_path,
        {
            "application_id": application_id,
            "expected_document_hash": named["expected_document_hash"],
            "profile_override": "account-manager",
        },
    )
    assert unnamed_analysis.status_code == 422, unnamed_analysis.text
    assert persisted_counts(database_engine) == before

    # A selection overlay naming both sources goes through; it is what moves the
    # document the next request still names.
    pinned = _post(
        api_paused, decisions_path, {**named, "pinned_fact_ids": ["sales.summary.new_business"]}
    )
    assert pinned.status_code == 201, pinned.text

    stale_document = _post(
        api_paused, decisions_path, {**named, "pinned_fact_ids": ["sales.summary.account"]}
    )
    assert stale_document.status_code == 409, stale_document.text
    assert stale_document.json()["code"] == "DOCUMENT_CHANGED"

    replacement = _existing_analysis(
        api_paused, application_id, transaction_manager, application_projection_reader
    )
    with transaction_manager.read() as tx:
        analyses_before = len(application_projection_reader.analyses(tx, application_id))
    stale_analysis = _post(
        api_paused,
        decisions_path,
        {
            **named,
            "expected_document_hash": pinned.json()["document_hash"],
            "emphasis_override": "new-business",
        },
    )
    assert stale_analysis.status_code == 409, stale_analysis.text
    assert "active JobAnalysis moved" in stale_analysis.text
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.analyses(tx, application_id)) == analyses_before
    assert _state(api_paused, application_id)["latest_analysis_id"] == replacement


# --- the document selection ---------------------------------------------------


def test_the_selection_change_returns_the_selection_and_its_readable_accounting(
    api_worker, transaction_manager, application_projection_reader
) -> None:
    """`200`, synchronously, with no provider anywhere near it (§14)."""
    application_id = _application(api_worker.services, "Deterministic Selection Co")
    analysis_id = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )

    initial = _document(api_worker, application_id)
    candidates = initial["selection"]["candidates"]
    assert initial["analysis_id"] == analysis_id
    assert candidates
    assert all(candidate["text"] for candidate in candidates)
    assert any(candidate["user_selectable"] for candidate in candidates)
    assert any(not candidate["user_selectable"] for candidate in candidates)
    pinned = next(
        candidate["fact_id"]
        for candidate in candidates
        if candidate["section"] == "Core Skills" and candidate["outcome"] == "omitted"
    )

    response = _post(
        api_worker,
        f"/applications/{application_id}/document/selection",
        {"expected_document_hash": initial["document_hash"], "pinned_fact_ids": [pinned]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == initial["id"]
    assert body["document_hash"] != initial["document_hash"]
    document = _document(api_worker, application_id)
    assert document["document_hash"] == body["document_hash"]
    assert document["analysis_id"] == analysis_id
    assert pinned in document["selection"]["selected_fact_ids"]
    assert document["selection"]["pinned_fact_ids"] == [pinned]
    assert document["selection"]["excluded_fact_ids"] == []
    assert {
        candidate["fact_id"]: candidate["outcome"]
        for candidate in document["selection"]["candidates"]
    }[pinned] == "pinned"


def test_a_later_analysis_reaches_the_document_only_through_build_from_analysis(
    api_worker, transaction_manager, application_projection_reader
) -> None:
    """§13 decision 3: the document is pinned; re-pinning is explicit and names the analysis."""
    application_id = _application(api_worker.services, "Historical Analysis Co")
    original = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )
    replacement = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )
    before = _document(api_worker, application_id)
    assert before["analysis_id"] == original

    rebuilt = _post(
        api_worker,
        f"/applications/{application_id}/document/build-from-analysis",
        {"expected_document_hash": before["document_hash"], "analysis_id": replacement},
    )

    assert rebuilt.status_code == 200, rebuilt.text
    state = _state(api_worker, application_id)
    assert state["document_analysis_id"] == replacement
    assert "DOCUMENT_ON_OLDER_ANALYSIS" not in {warning["code"] for warning in state["warnings"]}
    assert _document(api_worker, application_id)["content"] is None


def test_an_overlay_the_engine_cannot_honour_is_refused_rather_than_trimmed(
    api_worker, transaction_manager, application_projection_reader
) -> None:
    """Excluding a heading is refused at the boundary, not silently ignored.

    The alternative is a selection that quietly contains what the user asked to
    remove, or a document with bullets under no role.
    """
    application_id = _application(api_worker.services, "Impossible Overlay Co")
    _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )
    token = _document(api_worker, application_id)["document_hash"]

    response = _post(
        api_worker,
        f"/applications/{application_id}/document/selection",
        {"expected_document_hash": token, "excluded_fact_ids": ["sales.role.leader.title"]},
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "PRECONDITION_FAILED"
    assert _document(api_worker, application_id)["document_hash"] == token


def test_a_context_operation_blocks_voluntary_editing_and_the_command(
    api_paused, transaction_manager, application_projection_reader
) -> None:
    application_id = _application(api_paused.services, "Busy Context Co")
    analysis_id = _existing_analysis(
        api_paused, application_id, transaction_manager, application_projection_reader
    )
    with transaction_manager.read() as tx:
        before = len(application_projection_reader.analyses(tx, application_id))
    snapshot_id = _state(api_paused, application_id)["active_job_snapshot_id"]
    token = _document(api_paused, application_id)["document_hash"]

    queued = api_paused.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses",
        json={"job_snapshot_id": snapshot_id},
        headers={**MUTATION_HEADERS, "Idempotency-Key": "competing-analysis"},
    )
    assert queued.status_code == 202, queued.text
    state = _state(api_paused, application_id)
    assert "edit_matching_configuration" not in state["available_actions"]
    assert next(
        blocked["reasons"]
        for blocked in state["blocked_actions"]
        if blocked["action"] == "edit_matching_configuration"
    ) == ["MATCHING_CONTEXT_OPERATION_IN_PROGRESS"]

    refused = _post(
        api_paused,
        f"/analyses/{analysis_id}/apply-decisions",
        {
            "application_id": application_id,
            "expected_analysis_id": analysis_id,
            "expected_document_hash": token,
            "emphasis_override": "new-business",
        },
    )
    assert refused.status_code == 409, refused.text
    assert "context Operation is active" in refused.text
    with transaction_manager.read() as tx:
        after = len(application_projection_reader.analyses(tx, application_id))
    assert after == before
    assert _document(api_paused, application_id)["document_hash"] == token
