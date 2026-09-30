"""The AI routes of the document surface, over HTTP.

Three things are asserted here that nothing below the transport can assert: that
no route chooses facts apart from drafting (docs/decisions/ai-owned-selection.md),
that the regeneration routes are spelled the way §21 spells them, and that a stale
`expected_document_hash` is a `409` that calls no provider.

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
from cv_engine.domain.contracts.providers import ClaimProposal


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
    harness.fake_openai.script_draft()
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


def test_no_route_chooses_facts_apart_from_drafting(ai_api_worker) -> None:
    """The selection routes are gone, and the document carries no selection."""
    application_id = _drafted(ai_api_worker, "No Selection Co")
    document = _document(ai_api_worker, application_id)
    assert "selection" not in document
    base = f"/applications/{application_id}/document"
    for path in (f"{base}/selection", f"{base}/selection-proposals"):
        response = _post(ai_api_worker, path, {"expected_document_hash": document["document_hash"]})
        assert response.status_code in {404, 405}, (path, response.status_code)
    detail = ai_api_worker.client.get(f"{API_PREFIX}/applications/{application_id}").json()
    assert not {"update_selection", "propose_selection"} & set(detail["available_actions"])


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
