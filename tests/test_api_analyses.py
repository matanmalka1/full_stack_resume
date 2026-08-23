"""M3 Stage D: analyze, review decisions, and deterministic selection plans.

Stage D began with a verification rather than a mechanism. §13 requires every
successful analyze activation to commit an immutable JobAnalysis *and* its
initial deterministic SelectionPlan atomically, and the engine already did:
`save_analysis` writes both inside one SQLite transaction, and under an
Operation that transaction is the runner's own UnitOfWork. The first two tests
here are that evidence, held as a test rather than as a paragraph, so a later
change that splits the two writes fails instead of being argued about.
"""

from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB

from cv_engine.api.app import API_PREFIX
from cv_engine.api.schemas.operations import OperationResponse
from cv_engine.application.commands import IngestCommand


def _application(services, company: str, *, job_text: str = ACCOUNT_MANAGER_JOB) -> str:
    return services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Account Manager",
            job_text=job_text,
            acknowledged_duplicates=True,
        )
    ).application_id


def _analyze(harness, application_id: str, *, headers: dict[str, str] | None = None) -> dict:
    """Analyze the Application's active snapshot over HTTP and wait for it."""
    detail = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert detail.status_code == 200, detail.text
    snapshot_id = detail.json()["active_job_snapshot_id"]
    response = harness.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses",
        json={"job_snapshot_id": snapshot_id},
        headers={**MUTATION_HEADERS, **(headers or {})},
    )
    assert response.status_code == 202, response.text
    return harness.wait_for_operation(response.json()["id"])


def _outputs(finished: dict) -> dict[str, str]:
    return {output["output_type"]: output["output_id"] for output in finished["outputs"]}


def _state(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()


# --- the verification Stage D started from -----------------------------------


def test_a_successful_analysis_commits_its_analysis_and_initial_plan_together(
    api_worker,
) -> None:
    """§13: both records, one activation, and the plan bound to that analysis.

    This is what lets the no-review path call `create_draft` with explicit
    source IDs and no separate selection command, which is M3 acceptance item 2.
    """
    application_id = _application(api_worker.services, "Atomic Analysis Co")

    finished = _analyze(api_worker, application_id)

    assert finished["status"] == "succeeded"
    outputs = _outputs(finished)
    assert set(outputs) == {"job_analysis", "selection_plan"}
    assert all(output["active"] for output in finished["outputs"])

    plan = api_worker.services.repository.selection_plan(outputs["selection_plan"])
    assert plan.job_analysis_id == outputs["job_analysis"]
    assert plan.application_id == application_id

    state = _state(api_worker, application_id)
    assert state["active_analysis_id"] == outputs["job_analysis"]
    assert state["active_selection_plan_id"] == outputs["selection_plan"]
    assert state["preparation_state"] == "ready_to_draft"


def test_an_analysis_whose_plan_cannot_be_written_leaves_no_analysis_behind(
    services, monkeypatch
) -> None:
    """Atomic means atomic: the failure proves it, the success cannot.

    A passing happy path only shows both rows arrive. Only a failure part-way
    through shows they arrive together - and an Application left classified by
    an analysis with no plan would project `FACT_SELECTION_UNRESOLVED` forever,
    with no command able to reach the analysis that caused it.
    """
    from cv_engine.application.commands import AnalyzeCommand

    ingested = services.applications.ingest(
        IngestCommand(
            company="Rollback Analysis Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    )
    repository = services.repository
    before = len(repository.analyses(ingested.application_id))

    def refuse_plan(*_args, **_kwargs):
        raise RuntimeError("selection plan insert failed")

    monkeypatch.setattr(type(repository), "_insert_selection_plan", refuse_plan)

    with pytest.raises(RuntimeError):
        services.analysis.analyze(
            AnalyzeCommand(
                application_id=ingested.application_id,
                job_snapshot_id=ingested.job_snapshot_id,
            )
        )

    assert len(repository.analyses(ingested.application_id)) == before


# --- POST /applications/{id}/analyses ----------------------------------------


def test_analyze_is_accepted_as_an_operation_the_client_polls(api_worker) -> None:
    application_id = _application(api_worker.services, "Accepted Analysis Co")
    snapshot_id = _state(api_worker, application_id)["active_job_snapshot_id"]

    response = api_worker.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses",
        json={"job_snapshot_id": snapshot_id},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 202
    body = response.json()
    assert response.headers["Location"] == f"{API_PREFIX}/operations/{body['id']}"
    assert body["operation_type"] == "analyze_job"
    assert body["status"] == "queued"
    # Compared against the response model rather than a hand-written list: a
    # list would be written from the same belief that the narrowing works, which
    # is what let the runner record reach a client before Stage C.
    assert set(body) == set(OperationResponse.model_fields)

    assert api_worker.wait_for_operation(body["id"])["status"] == "succeeded"


def test_reusing_an_idempotency_key_returns_the_one_operation_it_created(api_worker) -> None:
    application_id = _application(api_worker.services, "Idempotent Analysis Co")
    snapshot_id = _state(api_worker, application_id)["active_job_snapshot_id"]
    request = {
        "json": {"job_snapshot_id": snapshot_id},
        "headers": {**MUTATION_HEADERS, "Idempotency-Key": "stage-d-analysis"},
    }

    first = api_worker.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses", **request
    )
    second = api_worker.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses", **request
    )

    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert api_worker.wait_for_operation(first.json()["id"])["status"] == "succeeded"


def test_needs_review_is_a_successful_outcome_carrying_both_records(api_worker) -> None:
    """NeedsReview is data, not a failure (§20, M3 acceptance item 3).

    The Operation succeeds, both immutable records exist, and what needs
    deciding is reported by the Application's review reasons - which name the
    command that resolves them.
    """
    application_id = _application(
        api_worker.services, "Needs Review Co", job_text=AMBIGUOUS_HEBREW_JOB
    )

    finished = _analyze(api_worker, application_id)

    assert finished["status"] == "succeeded"
    assert finished["failure_code"] is None
    outputs = _outputs(finished)
    assert set(outputs) == {"job_analysis", "selection_plan"}

    state = _state(api_worker, application_id)
    assert state["preparation_state"] == "needs_review"
    assert state["recommended_action"] == "apply_analysis_decisions"
    assert "apply_analysis_decisions" in state["available_actions"]
    assert {reason["code"] for reason in state["review_reasons"]}


# --- POST /analyses/{id}/decisions -------------------------------------------


def test_a_classification_decision_creates_a_new_analysis_and_its_initial_plan(
    api_worker,
) -> None:
    """The meaning branch, and the history it does not touch."""
    application_id = _application(
        api_worker.services, "Decided Classification Co", job_text=AMBIGUOUS_HEBREW_JOB
    )
    outputs = _outputs(_analyze(api_worker, application_id))
    original_analysis = api_worker.services.repository.get_analysis(outputs["job_analysis"])
    original_plan = api_worker.services.repository.selection_plan(outputs["selection_plan"])

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/decisions",
        json={
            "application_id": application_id,
            "profile_override": "account-manager",
            "accept_low_fit": True,
        },
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_analysis"] is True
    assert body["job_analysis_id"] != outputs["job_analysis"]
    assert body["selection_plan_id"] != outputs["selection_plan"]
    assert body["analysis"]["user_override"] == {
        "profile": "account-manager",
        "fit": "accepted-low-fit",
    }
    assert body["plan"]["job_analysis_id"] == body["job_analysis_id"]

    # The analysis and plan the user decided against are untouched history.
    assert api_worker.services.repository.get_analysis(outputs["job_analysis"]) == original_analysis
    assert api_worker.services.repository.selection_plan(outputs["selection_plan"]) == original_plan

    state = _state(api_worker, application_id)
    assert state["active_analysis_id"] == body["job_analysis_id"]
    assert state["active_selection_plan_id"] == body["selection_plan_id"]
    assert state["review_reasons"] == []
    assert state["preparation_state"] == "ready_to_draft"


def test_a_fact_overlay_alone_creates_a_replacement_plan_for_the_same_analysis(
    api_worker,
) -> None:
    """The selection branch: a new plan, and the analysis left exactly as it was."""
    application_id = _application(api_worker.services, "Replacement Plan Co")
    outputs = _outputs(_analyze(api_worker, application_id))
    original = api_worker.services.repository.selection_plan(outputs["selection_plan"])
    original_analysis = api_worker.services.repository.get_analysis(outputs["job_analysis"])
    removed = next(
        candidate.fact_id
        for candidate in original.plan.candidates
        if candidate.section == "Core Skills" and candidate.outcome == "selected"
    )

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/decisions",
        json={"application_id": application_id, "excluded_fact_ids": [removed]},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_analysis"] is False
    assert body["job_analysis_id"] == outputs["job_analysis"]
    assert body["selection_plan_id"] != outputs["selection_plan"]
    assert body["plan"]["version_number"] == original.version_number + 1
    assert removed not in body["plan"]["plan"]["selected_fact_ids"]
    assert {
        candidate["fact_id"]: candidate["reason"]
        for candidate in body["plan"]["plan"]["candidates"]
    }[removed] == "excluded_by_user"

    assert api_worker.services.repository.get_analysis(outputs["job_analysis"]) == original_analysis
    assert api_worker.services.repository.selection_plan(outputs["selection_plan"]) == original


def test_a_submission_carrying_both_kinds_of_decision_is_refused(api_worker) -> None:
    """The new analysis has its own initial plan, built from accounting the user
    has not seen. Carrying the overlay across would attach their decision to a
    different candidate set, so the client is told to send it separately."""
    application_id = _application(
        api_worker.services, "Both Branches Co", job_text=AMBIGUOUS_HEBREW_JOB
    )
    outputs = _outputs(_analyze(api_worker, application_id))

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/decisions",
        json={
            "application_id": application_id,
            "profile_override": "account-manager",
            "excluded_fact_ids": ["sales.achievement.retention"],
        },
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "PRECONDITION_FAILED"


def test_a_submission_that_changes_nothing_is_refused(api_worker) -> None:
    """An empty form would otherwise create a second identical plan, putting a
    decision in the history that nobody made."""
    application_id = _application(api_worker.services, "Empty Decision Co")
    outputs = _outputs(_analyze(api_worker, application_id))

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/decisions",
        json={"application_id": application_id},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 412, response.text


@pytest.mark.parametrize(
    ("route", "payload_key"),
    [("decisions", "profile_override"), ("selection-plans", "expected_profile_version")],
    ids=["decisions", "selection-plans"],
)
def test_an_analysis_belonging_to_another_application_is_refused(
    api_worker, route: str, payload_key: str
) -> None:
    """Both IDs are explicit, so a mismatch is a named refusal rather than a
    decision landing on someone else's analysis."""
    owner = _application(api_worker.services, "Lineage Owner Co")
    other = _application(api_worker.services, "Lineage Other Co")
    analysis_id = _outputs(_analyze(api_worker, owner))["job_analysis"]

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{analysis_id}/{route}",
        json={"application_id": other, payload_key: "account-manager"},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "LINEAGE_BROKEN"


@pytest.mark.parametrize("route", ["decisions", "selection-plans"])
def test_an_unknown_analysis_is_a_not_found(api_worker, route: str) -> None:
    application_id = _application(api_worker.services, f"Unknown Analysis {route} Co")

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/does-not-exist/{route}",
        json={"application_id": application_id},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "UNKNOWN_RECORD"


# --- POST /analyses/{id}/selection-plans -------------------------------------


def test_the_deterministic_plan_endpoint_returns_the_plan_itself(api_worker) -> None:
    """`201`, synchronously, with no provider anywhere near it (§13)."""
    application_id = _application(api_worker.services, "Deterministic Plan Co")
    outputs = _outputs(_analyze(api_worker, application_id))
    original = api_worker.services.repository.selection_plan(outputs["selection_plan"])
    pinned = next(
        candidate.fact_id
        for candidate in original.plan.candidates
        if candidate.section == "Core Skills" and candidate.outcome == "omitted"
    )

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/selection-plans",
        json={"application_id": application_id, "pinned_fact_ids": [pinned]},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_analysis_id"] == outputs["job_analysis"]
    assert body["plan"]["id"] == body["selection_plan_id"]
    assert pinned in body["plan"]["plan"]["selected_fact_ids"]
    assert {
        candidate["fact_id"]: candidate["outcome"]
        for candidate in body["plan"]["plan"]["candidates"]
    }[pinned] == "pinned"
    assert (
        _state(api_worker, application_id)["active_selection_plan_id"]
        == (body["selection_plan_id"])
    )


def test_a_plan_built_against_knowledge_that_has_moved_is_refused(api_worker) -> None:
    """The optimistic check: the candidate accounting the user decided against
    is no longer the one this plan would contain."""
    application_id = _application(api_worker.services, "Moved Knowledge Co")
    analysis_id = _outputs(_analyze(api_worker, application_id))["job_analysis"]

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{analysis_id}/selection-plans",
        json={
            "application_id": application_id,
            "expected_profile_version": "a-version-that-never-existed",
        },
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 412, response.text
    assert "Profile store" in response.json()["detail"]


def test_an_overlay_the_engine_cannot_honour_is_refused_rather_than_trimmed(api_worker) -> None:
    """Excluding a heading is refused at the boundary, not silently ignored.

    The alternative is a plan that quietly contains what the user asked to
    remove, or a document with bullets under no role.
    """
    application_id = _application(api_worker.services, "Impossible Overlay Co")
    analysis_id = _outputs(_analyze(api_worker, application_id))["job_analysis"]

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{analysis_id}/selection-plans",
        json={
            "application_id": application_id,
            "excluded_fact_ids": ["sales.role.leader.title"],
        },
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "PRECONDITION_FAILED"
