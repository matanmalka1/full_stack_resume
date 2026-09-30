"""API review decisions against existing AI analyses.

§13 requires the first analysis activation to commit its immutable JobAnalysis *and*
the Application's CV document in one transaction. The focused tests here hold that
behavior as evidence, and the review decisions that follow: every decision -
Track, Profile, language, or Emphasis - creates a new analysis and leaves the
document where it is.
"""

from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS
from helpers import (
    ACCOUNT_MANAGER_JOB,
    REVIEW_DECISION_JOB,
    analysis_proposal,
    persisted_counts,
    seed_existing_analysis,
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


@pytest.mark.parametrize("decision", ["classification", "emphasis"])
def test_a_decision_creates_an_analysis_and_leaves_the_document(
    api_worker, transaction_manager, application_projection_reader, decision
) -> None:
    """One branch, one history rule.

    A Profile or an Emphasis decision is classification: a new immutable analysis,
    and the document stays on the analysis it was built from until it is rebuilt.
    The analysis decided against is untouched history.
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
        submitted = {"profile_override": "account-manager"}
    else:
        application_id = _application(api_worker.services, "Decided Emphasis Co")
        analysis_id = _existing_analysis(
            api_worker, application_id, transaction_manager, application_projection_reader
        )
        submitted = {"emphasis_override": "new-business"}
    with transaction_manager.read() as tx:
        original_analysis = application_projection_reader.analysis(tx, analysis_id)
    original_document = _document(api_worker, application_id)

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
    assert body["job_analysis_id"] != analysis_id
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
    # The document is pinned to the analysis it was built from (§13 decision 3).
    assert document == original_document
    assert state["document_analysis_id"] == analysis_id
    assert "DOCUMENT_ON_OLDER_ANALYSIS" in {warning["code"] for warning in state["warnings"]}
    if decision == "classification":
        assert body["analysis"]["user_override"] == {"profile": "account-manager"}
        # The hard gap is still there and still hard. It is information for the
        # user, not a question they must answer before the document exists.
        assert state["review_reasons"] == []
    else:
        assert body["analysis"]["emphasis"] == "new-business"
        assert body["analysis"]["user_override"] == {"emphasis": "new-business"}
        assert state["application"]["emphasis"] == "new-business"


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

    A fact overlay: there is no selection to decide, so the field is unknown and the
    request is refused before a command is built, leaving no row anywhere.

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
    overlay = _post(
        api_paused,
        decisions_path,
        {**named, "excluded_fact_ids": ["sales.achievement.retention"]},
    )
    assert overlay.status_code == 422, overlay.text
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
            "emphasis_override": "new-business",
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

    stale_document = _post(
        api_paused,
        decisions_path,
        {**named, "expected_document_hash": "0" * 64, "emphasis_override": "new-business"},
    )
    assert stale_document.status_code == 409, stale_document.text
    assert stale_document.json()["code"] == "DOCUMENT_CHANGED"
    assert persisted_counts(database_engine) == before

    # A decision naming both sources goes through, and makes the analysis it was
    # made against stale for the next request.
    applied = _post(api_paused, decisions_path, {**named, "emphasis_override": "new-business"})
    assert applied.status_code == 201, applied.text
    replacement = applied.json()["job_analysis_id"]
    with transaction_manager.read() as tx:
        analyses_before = len(application_projection_reader.analyses(tx, application_id))
    stale_analysis = _post(api_paused, decisions_path, {**named, "language_override": "he"})
    assert stale_analysis.status_code == 409, stale_analysis.text
    assert "active JobAnalysis moved" in stale_analysis.text
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.analyses(tx, application_id)) == analyses_before
    assert _state(api_paused, application_id)["latest_analysis_id"] == replacement


# --- the document's analysis pin ----------------------------------------------


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
