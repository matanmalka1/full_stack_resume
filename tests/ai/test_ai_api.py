"""The AI routes of the document surface, over HTTP.

Three things are asserted here that nothing below the transport can assert: that
the selection proposal is a `202` with the `Location` a client polls while the
deterministic selection change answers synchronously, that the regeneration routes
are spelled the way §21 spells them, and that a stale `expected_document_hash` is a
`409` that calls no provider.

The provider is the real adapter over the fake transport, so an AI route in these
tests goes through the queue, the worker, the runner, and the handler - which is
what makes a `202` mean anything.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS, analyze_offline
from fake_provider import FakeOpenAI
from helpers import ACCOUNT_MANAGER_JOB, stored_document

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand
from cv_engine.domain.contracts.providers import ClaimProposal, SelectionProposal


def _post(harness, path: str, body: dict, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body, headers={**MUTATION_HEADERS, **headers}
    )


def _document(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}/document")
    assert response.status_code == 200, response.text
    return response.json()


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


def _drafted(harness, company: str) -> str:
    application_id = _application(harness.services, company)
    analyze_offline(harness, application_id, ACCOUNT_MANAGER_JOB)
    token = _document(harness, application_id)["document_hash"]
    response = _post(
        harness,
        f"/applications/{application_id}/document/draft",
        {"expected_document_hash": token},
    )
    assert response.status_code == 202, response.text
    finished = harness.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    return application_id


def _canonical_claim(content):
    for section in content.sections:
        for claim in section.claims:
            if claim.claim_type == "canonical" and len(claim.fact_ids) == 1:
                return section, claim
    raise AssertionError("the drafted document has no canonical single-fact claim")


def test_the_selection_proposal_is_queued_and_the_selection_change_is_not(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    """§14: `propose_selection` is an AI Operation, `update_selection` synchronous.

    The proposal's provenance lands on the document's selection; a later
    deterministic change is the user's own and records no provenance.
    """
    application_id = _application(ai_api_worker.services, "Selection Modes Co")
    analyze_offline(ai_api_worker, application_id, ACCOUNT_MANAGER_JOB)
    document = _document(ai_api_worker, application_id)
    assert (document["selection"]["proposed_by"], document["selection"]["proposal_rationale"]) == (
        None,
        None,
    )
    base = f"/applications/{application_id}/document"

    fake_openai.script(
        "propose_selection_plan",
        SelectionProposal(
            pinned_fact_ids=document["selection"]["selected_fact_ids"][:1],
            excluded_fact_ids=[],
            rationale="Pinned the retention fact the posting leads with.",
        ),
    )
    queued = _post(
        ai_api_worker,
        f"{base}/selection-proposals",
        {"expected_document_hash": document["document_hash"]},
    )
    assert queued.status_code == 202, queued.text
    assert queued.headers["Location"].endswith(queued.json()["id"])
    finished = ai_api_worker.wait_for_operation(queued.json()["id"])
    assert finished["status"] == "succeeded", finished

    proposed = _document(ai_api_worker, application_id)
    assert proposed["selection"]["proposed_by"] == "ai"
    assert proposed["selection"]["proposal_rationale"] == (
        "Pinned the retention fact the posting leads with."
    )

    changed = _post(
        ai_api_worker,
        f"{base}/selection",
        {"expected_document_hash": proposed["document_hash"], "pinned_fact_ids": []},
    )
    assert changed.status_code == 200, changed.text
    assert "Location" not in changed.headers
    assert changed.headers["ETag"] == f'"{changed.json()["document_hash"]}"'
    assert _document(ai_api_worker, application_id)["selection"]["proposed_by"] is None


def test_a_selection_proposal_is_refused_once_content_exists(ai_api_worker) -> None:
    """Proposals apply only while the document has no content (§14)."""
    application_id = _drafted(ai_api_worker, "Late Proposal Co")
    token = _document(ai_api_worker, application_id)["document_hash"]
    refused = _post(
        ai_api_worker,
        f"/applications/{application_id}/document/selection-proposals",
        {"expected_document_hash": token},
    )
    assert refused.status_code == 412, refused.text


def test_regenerate_claim_is_accepted_at_the_specified_path_only_on_a_current_hash(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    """The lost-update rule, on the route rather than only in the service.

    A stale hash is a conflict that calls no provider; the current one is accepted
    as an Operation.
    """
    application_id = _drafted(ai_api_worker, "Claim Route Co")
    document = stored_document(ai_api_worker.services, application_id)
    _, claim = _canonical_claim(document.content)
    path = f"/applications/{application_id}/document/regenerate-claim"

    stale = _post(
        ai_api_worker, path, {"expected_document_hash": "0" * 64, "claim_id": claim.claim_id}
    )
    assert stale.status_code == 409, stale.text
    assert fake_openai.calls_for("regenerate_claim") == []

    fake_openai.script(
        "regenerate_claim",
        ClaimProposal(
            claim_id=claim.claim_id,
            text=claim.text,
            fact_ids=list(claim.fact_ids),
            rationale="r",
        ),
    )
    response = _post(
        ai_api_worker,
        path,
        {"expected_document_hash": document.document_hash, "claim_id": claim.claim_id},
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
