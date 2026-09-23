"""API review decisions and selection plans against existing AI analyses.

§13 requires every analysis activation to commit an immutable JobAnalysis *and*
its initial SelectionPlan atomically, and the engine does:
`save_analysis` writes both inside one database transaction. The focused tests
here hold that behavior as evidence.
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
from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.domain.contracts.analysis import (
    Requirement,
)
from cv_engine.infrastructure.persistence import analysis_sql


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
) -> dict[str, str]:
    """Seed an analysis record explicitly; these tests exercise later API decisions."""
    with transaction_manager.read() as tx:
        snapshot_id = application_projection_reader.latest_snapshot(tx, application_id)["id"]
    analysed = seed_existing_analysis(
        harness.services,
        AnalyzeCommand(application_id=application_id, job_snapshot_id=snapshot_id),
        **analysis_values,
    )
    return {
        "job_analysis": analysed.analysis_id,
        "selection_plan": analysed.selection_plan_id,
    }


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


# --- analysis activation ----------------------------------------------------


def test_post_analysis_uses_ai_operation_and_commits_both_records(
    ai_api_worker,
    fake_openai,
    requirement_concepts,
    transaction_manager,
    application_projection_reader,
) -> None:
    fake_openai.script(
        "propose_analysis",
        analysis_proposal(summary="account management role", keywords=["retention"]),
    )
    application_id = _application(ai_api_worker.services, "AI Operation Co")
    with transaction_manager.read() as tx:
        snapshot_id = application_projection_reader.latest_snapshot(tx, application_id)["id"]
    response = ai_api_worker.client.post(
        f"{API_PREFIX}/applications/{application_id}/analyses",
        json={"job_snapshot_id": snapshot_id},
        headers=MUTATION_HEADERS,
    )
    assert response.status_code == 202, response.text
    completed = ai_api_worker.wait_for_operation(response.json()["id"])
    assert completed["status"] == "succeeded", completed
    # Each scripted provider call (extraction, classification) also lands as
    # its own provider_response output, preserved for provenance alongside
    # the two immutable records the analysis actually commits.
    outputs = {item["output_type"]: item["output_id"] for item in completed["outputs"]}
    assert set(outputs) == {"job_analysis", "selection_plan", "provider_response"}
    assert all(item["active"] for item in completed["outputs"])
    with transaction_manager.read() as tx:
        plan = application_projection_reader.selection_plan(tx, outputs["selection_plan"])
    assert plan.job_analysis_id == outputs["job_analysis"]


def test_an_analysis_commits_its_analysis_and_initial_plan_together_or_not_at_all(
    api_paused, monkeypatch, transaction_manager, application_projection_reader
) -> None:
    """§13: both records, one activation, and the plan bound to that analysis.

    Atomic means atomic: only a failure part-way through shows the two rows
    arrive together, a passing happy path cannot. An Application left
    classified by an analysis with no plan would project
    `FACT_SELECTION_UNRESOLVED` forever, with no command able to reach the
    analysis that caused it. The success then lets the no-review path draft
    with explicit source IDs and no separate selection command.
    """
    application_id = _application(api_paused.services, "Atomic Analysis Co")
    with transaction_manager.read() as tx:
        before = len(application_projection_reader.analyses(tx, application_id))

    def refuse_plan(*_args, **_kwargs):
        raise RuntimeError("selection plan insert failed")

    monkeypatch.setattr(analysis_sql, "_insert_selection_plan", refuse_plan)
    with pytest.raises(RuntimeError):
        _existing_analysis(
            api_paused, application_id, transaction_manager, application_projection_reader
        )
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.analyses(tx, application_id)) == before

    monkeypatch.undo()
    outputs = _existing_analysis(
        api_paused, application_id, transaction_manager, application_projection_reader
    )
    assert set(outputs) == {"job_analysis", "selection_plan"}

    with transaction_manager.read() as tx:
        plan = application_projection_reader.selection_plan(tx, outputs["selection_plan"])
    assert plan.job_analysis_id == outputs["job_analysis"]
    assert plan.application_id == application_id

    state = _state(api_paused, application_id)
    assert state["active_analysis_id"] == outputs["job_analysis"]
    assert state["active_selection_plan_id"] == outputs["selection_plan"]
    assert state["preparation_state"] == "ready_to_draft"


# --- POST /analyses/{id}/apply-decisions -------------------------------------------


@pytest.mark.parametrize("decision", ["classification", "fact_overlay", "emphasis"])
def test_a_decision_writes_new_records_and_leaves_the_decided_against_ones_untouched(
    api_worker, transaction_manager, application_projection_reader, decision
) -> None:
    """Three branches, one history rule.

    A classification decision is the meaning branch: a new analysis with its own
    initial plan. A fact overlay or an emphasis decision is the selection
    branch: a replacement plan for the same analysis, since emphasis selects
    policy and does not rewrite analysis meaning. In every branch the analysis
    and plan the user decided against are untouched history.
    """
    if decision == "classification":
        application_id = _application(
            api_worker.services, "Decided Classification Co", job_text=REVIEW_DECISION_JOB
        )
        outputs = _existing_analysis(
            api_worker,
            application_id,
            transaction_manager,
            application_projection_reader,
            **REVIEW_ANALYSIS,
        )
    else:
        application_id = _application(api_worker.services, f"Decided {decision} Co")
        outputs = _existing_analysis(
            api_worker, application_id, transaction_manager, application_projection_reader
        )
    with transaction_manager.read() as tx:
        original_analysis = application_projection_reader.analysis(tx, outputs["job_analysis"])
        original_plan = application_projection_reader.selection_plan(tx, outputs["selection_plan"])
    removed = None
    if decision == "classification":
        submitted = {"profile_override": "account-manager"}
    elif decision == "fact_overlay":
        removed = next(
            candidate.fact_id
            for candidate in original_plan.plan.candidates
            if candidate.section == "Core Skills" and candidate.outcome == "selected"
        )
        submitted = {"excluded_fact_ids": [removed]}
    else:
        submitted = {"emphasis_override": "new-business"}

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
        json={
            "application_id": application_id,
            "expected_analysis_id": outputs["job_analysis"],
            "expected_selection_plan_id": outputs["selection_plan"],
            **submitted,
        },
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    creates_analysis = decision == "classification"
    assert body["created_analysis"] is creates_analysis
    assert (body["job_analysis_id"] != outputs["job_analysis"]) is creates_analysis
    assert body["selection_plan_id"] != outputs["selection_plan"]
    assert body["plan"]["job_analysis_id"] == body["job_analysis_id"]

    with transaction_manager.read() as tx:
        assert (
            application_projection_reader.analysis(tx, outputs["job_analysis"]) == original_analysis
        )
        assert (
            application_projection_reader.selection_plan(tx, outputs["selection_plan"])
            == original_plan
        )

    state = _state(api_worker, application_id)
    assert state["active_analysis_id"] == body["job_analysis_id"]
    assert state["active_selection_plan_id"] == body["selection_plan_id"]
    assert body["state"]["active_analysis_id"] == state["active_analysis_id"]
    assert body["state"]["active_selection_plan_id"] == state["active_selection_plan_id"]
    assert body["state"]["available_actions"] == state["available_actions"]
    assert body["state"]["recommended_action"] == state["recommended_action"]

    if decision == "classification":
        assert body["analysis"]["user_override"] == {"profile": "account-manager"}
        # The hard gap is still there and still hard. It is information for the
        # user, not a question they must answer before the document exists.
        assert state["review_reasons"] == []
        assert state["preparation_state"] == "ready_to_draft"
    elif decision == "fact_overlay":
        assert body["plan"]["version_number"] == original_plan.version_number + 1
        assert removed not in body["plan"]["plan"]["selected_fact_ids"]
        assert {
            candidate["fact_id"]: candidate["reason"]
            for candidate in body["plan"]["plan"]["candidates"]
        }[removed] == "excluded_by_user"
    else:
        assert body["plan"]["plan"]["emphasis"] == "new-business"
        assert body["plan"]["plan"]["emphasis_override"] == "new-business"
        assert state["application"]["emphasis"] == "new-business"
        drafted = api_worker.services.drafts.draft(
            DraftCommand(
                application_id=application_id,
                job_analysis_id=outputs["job_analysis"],
                selection_plan_id=body["selection_plan_id"],
            )
        )
        with transaction_manager.read() as tx:
            working = application_projection_reader.working_draft(tx, drafted.working_draft_id)
        assert working.source.emphasis.value == "new-business"
        assert working.source.selection is not None
        assert working.source.selection.emphasis_override is not None


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
    """Every refusal of a decision or plan request, none of which is a 500.

    Both kinds at once: a fact overlay is decided against candidate accounting
    the new analysis has not produced yet, so riding it on a classification
    decision would attach the user's decision to a different candidate set. It
    stays a second command, and the refusal leaves no row anywhere.

    Nothing at all: an empty form would create a second identical plan, putting
    a decision in the history that nobody made.

    A value outside its closed set: refused as a request error before a command
    is built, on both routes that accept a classification override. Untyped, it
    reached `ProfileName(...)` as a bare `ValueError`, so ordinary input
    answered with a 500.

    Knowledge that moved: the candidate accounting the user decided against is
    no longer the one the plan would contain.

    Unnamed or moved sources: a decision names the analysis and plan it was
    made against, or it would be applied to whatever is active when it
    arrives. A missing plan token is a malformed request (412); a token naming
    a plan or analysis that has since moved is the lost race (409), and the
    refused analysis write leaves the replacement active.
    """
    application_id = _application(
        api_paused.services, "Refused Decisions Co", job_text=RIVERSIDE_POSTING
    )
    outputs = _existing_analysis(
        api_paused,
        application_id,
        transaction_manager,
        application_projection_reader,
        **RIVERSIDE_ANALYSIS,
    )
    analysis_id = outputs["job_analysis"]
    decisions_path = f"{API_PREFIX}/analyses/{analysis_id}/apply-decisions"
    plans_path = f"{API_PREFIX}/analyses/{analysis_id}/selection-plans"
    named = {
        "application_id": application_id,
        "expected_analysis_id": analysis_id,
        "expected_selection_plan_id": outputs["selection_plan"],
    }

    def post(path: str, payload: dict):
        return api_paused.client.post(path, json=payload, headers=MUTATION_HEADERS)

    before = persisted_counts(database_engine)
    both = post(
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

    empty = post(decisions_path, named)
    assert empty.status_code == 412, empty.text

    snapshot_id = _state(api_paused, application_id)["active_job_snapshot_id"]
    for path, payload in [
        (decisions_path, {**named, "profile_override": "not-a-profile"}),
        (
            f"{API_PREFIX}/applications/{application_id}/analyses",
            {"job_snapshot_id": snapshot_id, "profile_override": "not-a-profile"},
        ),
    ]:
        refused = post(path, payload)
        assert refused.status_code == 422, (path, refused.text)

    for expected_field, expected_source in [
        ("expected_facts_version", "Facts store"),
        ("expected_profile_version", "Profile store"),
    ]:
        moved = post(
            plans_path,
            {"application_id": application_id, expected_field: "a-version-that-never-existed"},
        )
        assert moved.status_code == 412, moved.text
        assert expected_source in moved.json()["detail"]

    unnamed_plan = post(
        decisions_path,
        {
            "application_id": application_id,
            "expected_analysis_id": analysis_id,
            "pinned_fact_ids": ["sales.summary.new_business"],
        },
    )
    assert unnamed_plan.status_code == 412, unnamed_plan.text
    assert "expected_selection_plan_id" in unnamed_plan.text

    unnamed_analysis = post(
        decisions_path,
        {
            "application_id": application_id,
            "expected_selection_plan_id": outputs["selection_plan"],
            "profile_override": "account-manager",
        },
    )
    assert unnamed_analysis.status_code == 422, unnamed_analysis.text

    # A selection overlay naming both sources goes through; it is what moves
    # the plan the next request still names.
    pinned = post(decisions_path, {**named, "pinned_fact_ids": ["sales.summary.new_business"]})
    assert pinned.status_code == 201, pinned.text

    stale_plan = post(decisions_path, {**named, "pinned_fact_ids": ["sales.summary.account"]})
    assert stale_plan.status_code == 409, stale_plan.text
    assert "moved since this decision was made" in stale_plan.text

    replacement = _existing_analysis(
        api_paused, application_id, transaction_manager, application_projection_reader
    )
    with transaction_manager.read() as tx:
        analyses_before = len(application_projection_reader.analyses(tx, application_id))
    stale_analysis = post(
        decisions_path,
        {
            **named,
            "expected_selection_plan_id": pinned.json()["selection_plan_id"],
            "emphasis_override": "new-business",
        },
    )
    assert stale_analysis.status_code == 409, stale_analysis.text
    assert "active JobAnalysis moved" in stale_analysis.text
    with transaction_manager.read() as tx:
        assert len(application_projection_reader.analyses(tx, application_id)) == analyses_before
    assert _state(api_paused, application_id)["active_analysis_id"] == replacement["job_analysis"]


# --- POST /analyses/{id}/selection-plans -------------------------------------


def test_the_deterministic_plan_endpoint_returns_the_plan_and_its_readable_accounting(
    api_worker, transaction_manager, application_projection_reader
) -> None:
    """`201`, synchronously, with no provider anywhere near it (§13)."""
    application_id = _application(api_worker.services, "Deterministic Plan Co")
    outputs = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )

    initial = api_worker.client.get(f"{API_PREFIX}/selection-plans/{outputs['selection_plan']}")
    assert initial.status_code == 200, initial.text
    initial_body = initial.json()
    assert initial_body["id"] == outputs["selection_plan"]
    assert initial_body["job_analysis_id"] == outputs["job_analysis"]
    assert initial_body["candidates"]
    assert all(candidate["text"] for candidate in initial_body["candidates"])
    assert any(candidate["user_selectable"] for candidate in initial_body["candidates"])
    assert any(not candidate["user_selectable"] for candidate in initial_body["candidates"])

    with transaction_manager.read() as tx:
        original = application_projection_reader.selection_plan(tx, outputs["selection_plan"])
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
    detail = api_worker.client.get(f"{API_PREFIX}/selection-plans/{body['selection_plan_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["pinned_fact_ids"] == [pinned]
    assert detail.json()["excluded_fact_ids"] == []
    assert (
        _state(api_worker, application_id)["active_selection_plan_id"]
        == (body["selection_plan_id"])
    )


def test_a_selection_plan_cannot_make_a_historical_analysis_active_by_accident(
    api_worker, transaction_manager, application_projection_reader
) -> None:
    application_id = _application(api_worker.services, "Historical Analysis Co")
    original = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )
    replacement = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{original['job_analysis']}/selection-plans",
        json={"application_id": application_id},
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 409, response.text
    state = _state(api_worker, application_id)
    assert state["active_analysis_id"] == replacement["job_analysis"]
    assert state["active_selection_plan_id"] == replacement["selection_plan"]


def test_an_overlay_the_engine_cannot_honour_is_refused_rather_than_trimmed(
    api_worker, transaction_manager, application_projection_reader
) -> None:
    """Excluding a heading is refused at the boundary, not silently ignored.

    The alternative is a plan that quietly contains what the user asked to
    remove, or a document with bullets under no role.
    """
    application_id = _application(api_worker.services, "Impossible Overlay Co")
    analysis_id = _existing_analysis(
        api_worker, application_id, transaction_manager, application_projection_reader
    )["job_analysis"]

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


def test_a_context_operation_blocks_voluntary_editing_and_the_command(
    api_paused, transaction_manager, application_projection_reader
) -> None:
    application_id = _application(api_paused.services, "Busy Context Co")
    active = _existing_analysis(
        api_paused, application_id, transaction_manager, application_projection_reader
    )
    with transaction_manager.read() as tx:
        before = len(application_projection_reader.analyses(tx, application_id))
    snapshot_id = _state(api_paused, application_id)["active_job_snapshot_id"]

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

    refused = api_paused.client.post(
        f"{API_PREFIX}/analyses/{active['job_analysis']}/apply-decisions",
        json={
            "application_id": application_id,
            "expected_analysis_id": active["job_analysis"],
            "expected_selection_plan_id": active["selection_plan"],
            "emphasis_override": "new-business",
        },
        headers=MUTATION_HEADERS,
    )
    assert refused.status_code == 409, refused.text
    assert "context Operation is active" in refused.text
    with transaction_manager.read() as tx:
        after = len(application_projection_reader.analyses(tx, application_id))
    assert after == before
