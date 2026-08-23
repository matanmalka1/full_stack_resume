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

from api_harness import MUTATION_HEADERS
from fake_provider import FakeOpenAI, HTTPStatus
from helpers import ACCOUNT_MANAGER_JOB

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand
from cv_engine.domain.models import ClaimProposal, SectionProposal, SelectionProposal


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
        )
    ).application_id


def _analyze(harness, application_id: str) -> dict[str, str]:
    detail = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
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
    finished = harness.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    return {output["output_type"]: output["output_id"] for output in finished["outputs"]}[
        "working_draft"
    ]


def _drafted(harness, company: str):
    application_id = _application(harness.services, company)
    sources = _analyze(harness, application_id)
    working_draft_id = _generate(harness, application_id, sources)
    working = harness.services.repository.working_draft(working_draft_id)
    return application_id, sources, working


def _canonical_claim(working):
    for section in working.source.sections:
        for claim in section.claims:
            if claim.claim_type == "canonical" and len(claim.fact_ids) == 1:
                return section, claim
    raise AssertionError("the drafted document has no canonical single-fact claim")


def test_deterministic_selection_plan_mode_is_still_201_with_the_plan_itself(
    ai_api_worker,
) -> None:
    application_id = _application(ai_api_worker.services, "Deterministic Plan Co")
    sources = _analyze(ai_api_worker, application_id)
    response = _post(
        ai_api_worker,
        f"/analyses/{sources['job_analysis']}/selection-plans",
        {"application_id": application_id, "mode": "deterministic"},
    )
    assert response.status_code == 201, response.text
    assert "Location" not in response.headers
    assert response.json()["plan"]["id"] == response.json()["selection_plan_id"]


def test_ai_selection_plan_mode_is_202_with_a_location_on_the_same_route(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    """§13 and architecture §12: one route, two statuses, decided per request."""
    application_id = _application(ai_api_worker.services, "AI Plan Co")
    sources = _analyze(ai_api_worker, application_id)
    plan = ai_api_worker.services.repository.selection_plan(sources["selection_plan"])
    fake_openai.script(
        "propose_selection_plan",
        SelectionProposal(
            pinned_fact_ids=plan.plan.selected_fact_ids[:1],
            excluded_fact_ids=[],
            rationale="r",
        ),
    )

    response = _post(
        ai_api_worker,
        f"/analyses/{sources['job_analysis']}/selection-plans",
        {"application_id": application_id, "mode": "ai"},
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished
    assert any(output["output_type"] == "selection_plan" for output in finished["outputs"])


def test_ai_selection_plan_mode_refuses_a_user_overlay_in_the_same_request(
    ai_api_worker,
) -> None:
    application_id = _application(ai_api_worker.services, "Both Answers Co")
    sources = _analyze(ai_api_worker, application_id)
    response = _post(
        ai_api_worker,
        f"/analyses/{sources['job_analysis']}/selection-plans",
        {"application_id": application_id, "mode": "ai", "pinned_fact_ids": ["a.b"]},
    )
    assert response.status_code == 412, response.text


def test_regenerate_section_is_accepted_at_the_specified_path(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    application_id, sources, working = _drafted(ai_api_worker, "Section Route Co")
    section, claim = _canonical_claim(working)
    fake_openai.script(
        "regenerate_section",
        SectionProposal(
            section=section.name,
            claims=[
                {
                    "section": section.name,
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "fact_ids": list(claim.fact_ids),
                }
            ],
            rationale="r",
        ),
    )
    response = _post(
        ai_api_worker,
        f"/working-drafts/{working.id}/regenerate-section",
        {
            "application_id": application_id,
            "expected_edit_version": working.edit_version,
            "expected_content_hash": working.content_hash,
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            "section": section.name,
        },
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished


def test_regenerate_claim_is_accepted_at_the_specified_path(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    application_id, sources, working = _drafted(ai_api_worker, "Claim Route Co")
    _section, claim = _canonical_claim(working)
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
        f"/working-drafts/{working.id}/regenerate-claim",
        {
            "application_id": application_id,
            "expected_edit_version": working.edit_version,
            "expected_content_hash": working.content_hash,
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            "claim_id": claim.claim_id,
        },
    )
    assert response.status_code == 202, response.text
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "succeeded", finished


def test_a_stale_etag_on_regeneration_is_a_conflict_and_calls_no_provider(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    """The lost-update rule, on the route rather than only in the service."""
    application_id, sources, working = _drafted(ai_api_worker, "Stale Route Co")
    _section, claim = _canonical_claim(working)
    response = _post(
        ai_api_worker,
        f"/working-drafts/{working.id}/regenerate-claim",
        {
            "application_id": application_id,
            "expected_edit_version": working.edit_version + 3,
            "expected_content_hash": working.content_hash,
            "job_analysis_id": sources["job_analysis"],
            "selection_plan_id": sources["selection_plan"],
            "claim_id": claim.claim_id,
        },
    )
    assert response.status_code == 409, response.text
    assert fake_openai.calls_for("regenerate_claim") == []


def test_a_failed_ai_operation_is_a_successful_poll_reporting_the_failure(
    ai_api_worker, fake_openai: FakeOpenAI
) -> None:
    """A provider failure is data on the Operation, not a 5xx on the route."""
    application_id = _application(ai_api_worker.services, "Failed Plan Co")
    sources = _analyze(ai_api_worker, application_id)
    fake_openai.script("propose_selection_plan", HTTPStatus(400))

    response = _post(
        ai_api_worker,
        f"/analyses/{sources['job_analysis']}/selection-plans",
        {"application_id": application_id, "mode": "ai"},
    )
    assert response.status_code == 202, response.text
    finished = ai_api_worker.wait_for_operation(response.json()["id"])
    assert finished["status"] == "failed"
    assert finished["failure_code"] == "PROVIDER_REFUSED"
    assert "sk-" not in finished["safe_failure_detail"]
