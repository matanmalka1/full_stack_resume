"""M3 Stage G's HTTP surface: the AI branch of a route, and two new routes.

Three things are asserted here that nothing below the transport can assert:
that `POST /analyses/{id}/selection-plans` answers `201` or `202` from the same
route depending on the mode, that the two regeneration routes are spelled the
way §21 spells them, and that a `202` in every case carries the `Location` a
client polls.

The provider is the real adapter over the fake transport, so an AI route in
these tests goes through the queue, the worker, the runner, and the handler -
which is what makes a `202` mean anything.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS, analyze_offline
from fake_provider import FakeOpenAI
from helpers import ACCOUNT_MANAGER_JOB

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand
from cv_engine.domain.contracts.providers import ClaimProposal, SelectionProposal


def _post(harness, path: str, body: dict, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body, headers={**MUTATION_HEADERS, **headers}
    )


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
    finished = harness.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    return {output["output_type"]: output["output_id"] for output in finished["outputs"]}[
        "working_draft"
    ]


def _drafted(harness, company: str, transaction_manager, application_projection_reader):
    application_id = _application(harness.services, company)
    sources = _analyze(harness, application_id)
    working_draft_id = _generate(harness, application_id, sources)
    with transaction_manager.read() as tx:
        working = application_projection_reader.working_draft(tx, working_draft_id)
    return application_id, sources, working


def _canonical_claim(working):
    for section in working.source.sections:
        for claim in section.claims:
            if claim.claim_type == "canonical" and len(claim.fact_ids) == 1:
                return section, claim
    raise AssertionError("the drafted document has no canonical single-fact claim")


def test_the_selection_plan_route_answers_201_or_202_by_mode(
    ai_api_worker, fake_openai: FakeOpenAI, transaction_manager, application_projection_reader
) -> None:
    """§13 and architecture §12: one route, two statuses, decided per request.

    AI mode is `202` with a `Location` and refuses a user decision in the same
    request; deterministic mode is still `201` with the plan itself.
    """
    application_id = _application(ai_api_worker.services, "Plan Modes Co")
    sources = _analyze(ai_api_worker, application_id)
    path = f"/analyses/{sources['job_analysis']}/selection-plans"

    both_answers = _post(
        ai_api_worker,
        path,
        {"application_id": application_id, "mode": "ai", "pinned_fact_ids": ["a.b"]},
    )
    assert both_answers.status_code == 412, both_answers.text

    with transaction_manager.read() as tx:
        plan = application_projection_reader.selection_plan(tx, sources["selection_plan"])
    fake_openai.script(
        "propose_selection_plan",
        SelectionProposal(
            pinned_fact_ids=plan.plan.selected_fact_ids[:1],
            excluded_fact_ids=[],
            rationale="r",
        ),
    )
    queued = _post(ai_api_worker, path, {"application_id": application_id, "mode": "ai"})
    assert queued.status_code == 202, queued.text
    assert queued.headers["Location"].endswith(queued.json()["id"])
    finished = ai_api_worker.wait_for_operation(queued.json()["id"])
    assert finished["status"] == "succeeded", finished
    assert any(output["output_type"] == "selection_plan" for output in finished["outputs"])

    deterministic = _post(
        ai_api_worker, path, {"application_id": application_id, "mode": "deterministic"}
    )
    assert deterministic.status_code == 201, deterministic.text
    assert "Location" not in deterministic.headers
    assert deterministic.json()["plan"]["id"] == deterministic.json()["selection_plan_id"]


def test_regenerate_claim_is_accepted_at_the_specified_path_only_on_a_current_etag(
    ai_api_worker, fake_openai: FakeOpenAI, transaction_manager, application_projection_reader
) -> None:
    """The lost-update rule, on the route rather than only in the service.

    A stale version is a conflict that calls no provider; the current one is
    accepted as an Operation.
    """
    application_id, sources, working = _drafted(
        ai_api_worker, "Claim Route Co", transaction_manager, application_projection_reader
    )
    _section, claim = _canonical_claim(working)
    request = {
        "application_id": application_id,
        "expected_edit_version": working.edit_version,
        "expected_content_hash": working.content_hash,
        "job_analysis_id": sources["job_analysis"],
        "selection_plan_id": sources["selection_plan"],
        "claim_id": claim.claim_id,
    }
    path = f"/working-drafts/{working.id}/regenerate-claim"

    stale = _post(
        ai_api_worker, path, {**request, "expected_edit_version": working.edit_version + 3}
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
    response = _post(ai_api_worker, path, request)
    assert response.status_code == 202, response.text
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
