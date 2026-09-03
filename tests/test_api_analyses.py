"""M3 Stage D: analyze, review decisions, and deterministic selection plans.

Stage D began with a verification rather than a mechanism. §13 requires every
successful analyze activation to commit an immutable JobAnalysis *and* its
initial deterministic SelectionPlan atomically, and the engine already did:
`save_analysis` writes both inside one database transaction, and under an
Operation that transaction is the runner's own UnitOfWork. The first two tests
here are that evidence, held as a test rather than as a paragraph, so a later
change that splits the two writes fails instead of being argued about.
"""

from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand


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
            client="web",
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


# --- POST /analyses/{id}/apply-decisions -------------------------------------------


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
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
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

    # The classification is settled, but the hard gap is a separate decision and
    # is deliberately still standing: `accepted-low-fit` answers low Fit alone.
    # It used to clear every hard gap with it.
    assert {reason["code"] for reason in state["review_reasons"]} == {"HARD_GAP_REQUIRES_DECISION"}
    accepted = _accept(
        api_worker,
        application_id,
        body["job_analysis_id"],
        _hard_gap_requirement_ids(api_worker, body["job_analysis_id"]),
        expected_selection_plan_id=body["selection_plan_id"],
    )
    assert accepted.status_code == 201, accepted.text
    state = _state(api_worker, application_id)
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
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
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


def test_the_api_refuses_decision_submissions_it_cannot_act_on(api_worker) -> None:
    """Three refusals of a classification submission, none of which is a 500.

    Both kinds at once: the new analysis has its own initial plan, built from
    accounting the user has not seen. Carrying the overlay across would attach
    their decision to a different candidate set, so the client is told to send
    it separately.

    Nothing at all: an empty form would create a second identical plan, putting
    a decision in the history that nobody made.

    A value outside its closed set: refused as a request error before a command
    is built. Untyped, it reached `ProfileName(...)` as a bare `ValueError` that
    no handler catches, so ordinary user input answered with a 500.
    """
    application_id = _application(
        api_worker.services, "Both Branches Co", job_text=AMBIGUOUS_HEBREW_JOB
    )
    outputs = _outputs(_analyze(api_worker, application_id))

    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
        json={
            "application_id": application_id,
            "profile_override": "account-manager",
            "excluded_fact_ids": ["sales.achievement.retention"],
        },
        headers=MUTATION_HEADERS,
    )

    assert response.status_code == 412, response.text
    assert response.json()["code"] == "PRECONDITION_FAILED"

    empty_application_id = _application(api_worker.services, "Empty Decision Co")
    empty_outputs = _outputs(_analyze(api_worker, empty_application_id))

    empty = api_worker.client.post(
        f"{API_PREFIX}/analyses/{empty_outputs['job_analysis']}/apply-decisions",
        json={"application_id": empty_application_id},
        headers=MUTATION_HEADERS,
    )

    assert empty.status_code == 412, empty.text

    # Both routes that accept a classification override, so neither can be
    # typed and the other left open.
    snapshot_id = _state(api_worker, application_id)["active_job_snapshot_id"]
    outside_the_set = [
        (
            f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
            {"application_id": application_id, "profile_override": "not-a-profile"},
        ),
        (
            f"{API_PREFIX}/applications/{application_id}/analyses",
            {"job_snapshot_id": snapshot_id, "profile_override": "not-a-profile"},
        ),
    ]
    for path, payload in outside_the_set:
        refused = api_worker.client.post(path, json=payload, headers=MUTATION_HEADERS)

        assert refused.status_code == 422, (path, refused.text)


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


def _hard_gap_requirement_ids(api_worker, analysis_id: str) -> list[str]:
    analysis = api_worker.services.repository.get_analysis(analysis_id)["analysis"]
    return [
        gap.requirement_id
        for gap in analysis.gaps
        if gap.severity == "hard" and gap.requirement_id is not None
    ]


def _active_plan_id(api_worker, application_id: str) -> str:
    return api_worker.services.repository.latest_selection_plan(application_id).id


def _accept(api_worker, application_id, analysis_id, requirement_ids, **extra):
    """Accept gaps the way a client must: naming the plan the user was shown.

    `expected_selection_plan_id` is required once anything is accepted, so a
    helper that omitted it would only ever exercise the refusal.
    """
    body = {
        "application_id": application_id,
        "accepted_requirement_ids": list(requirement_ids),
        **extra,
    }
    body.setdefault("expected_selection_plan_id", _active_plan_id(api_worker, application_id))
    return api_worker.client.post(
        f"{API_PREFIX}/analyses/{analysis_id}/apply-decisions",
        json=body,
        headers=MUTATION_HEADERS,
    )


RIVERSIDE_POSTING = (
    "About the job\n"
    "Riverside built an AI-powered platform for content creators.\n\n"
    "Requirements:\n\n"
    "1+ years of sales closing experience in the market at a technology company, "
    "with a track record of top performance (must).\n"
    "Native English speaker (multiple languages are a plus).\n"
)


def test_accepting_a_gap_creates_a_plan_and_never_a_new_analysis(api_worker) -> None:
    """Acceptance is a selection decision, so the analysis stays reusable.

    It does not change what the requirement means, what covers it, or how the
    job is classified - only that the user proceeds despite it.
    """
    application_id = _application(api_worker.services, "Riverside", job_text=RIVERSIDE_POSTING)
    outputs = _outputs(_analyze(api_worker, application_id))
    analysis_id = outputs["job_analysis"]
    hard = _hard_gap_requirement_ids(api_worker, analysis_id)
    assert len(hard) >= 2, "the posting must produce more than one hard gap"

    response = _accept(api_worker, application_id, analysis_id, hard[:1], acceptance_reason="ok")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_analysis"] is False
    assert body["job_analysis_id"] == analysis_id
    assert body["selection_plan_id"] != outputs["selection_plan"]

    plan = api_worker.services.repository.selection_plan(body["selection_plan_id"])
    assert [gap.requirement_id for gap in plan.accepted_gaps] == hard[:1]
    assert plan.accepted_gaps[0].job_analysis_id == analysis_id
    assert plan.accepted_gaps[0].actor
    assert plan.accepted_gaps[0].accepted_at
    assert plan.accepted_gaps[0].reason == "ok"


def test_accepting_one_gap_leaves_the_others_unresolved(api_worker) -> None:
    """The failure this stage exists to remove: one decision clearing all of them."""
    application_id = _application(api_worker.services, "Riverside Two", job_text=RIVERSIDE_POSTING)
    outputs = _outputs(_analyze(api_worker, application_id))
    analysis_id = outputs["job_analysis"]
    hard = _hard_gap_requirement_ids(api_worker, analysis_id)

    _accept(api_worker, application_id, analysis_id, hard[:1])
    state = _state(api_worker, application_id)
    codes = {reason["code"] for reason in state["review_reasons"]}
    assert "HARD_GAP_REQUIRES_DECISION" in codes, "the remaining gap still needs a decision"

    _accept(api_worker, application_id, analysis_id, hard[1:])
    state = _state(api_worker, application_id)
    codes = {reason["code"] for reason in state["review_reasons"]}
    assert "HARD_GAP_REQUIRES_DECISION" not in codes


def test_acceptance_accumulates_rather_than_replacing(api_worker) -> None:
    """A second decision must not silently retract the first."""
    application_id = _application(
        api_worker.services, "Riverside Three", job_text=RIVERSIDE_POSTING
    )
    outputs = _outputs(_analyze(api_worker, application_id))
    analysis_id = outputs["job_analysis"]
    hard = _hard_gap_requirement_ids(api_worker, analysis_id)

    _accept(api_worker, application_id, analysis_id, hard[:1])
    second = _accept(api_worker, application_id, analysis_id, hard[1:])
    plan = api_worker.services.repository.selection_plan(second.json()["selection_plan_id"])
    assert sorted(gap.requirement_id for gap in plan.accepted_gaps) == sorted(hard)


def test_accepted_low_fit_no_longer_clears_a_hard_gap(api_worker) -> None:
    """One checkbox used to dismiss every deficiency, seen or not."""
    application_id = _application(api_worker.services, "Riverside Four", job_text=RIVERSIDE_POSTING)
    outputs = _outputs(_analyze(api_worker, application_id))
    response = api_worker.client.post(
        f"{API_PREFIX}/analyses/{outputs['job_analysis']}/apply-decisions",
        json={"application_id": application_id, "accept_low_fit": True},
        headers=MUTATION_HEADERS,
    )
    assert response.status_code == 201, response.text
    state = _state(api_worker, application_id)
    codes = {reason["code"] for reason in state["review_reasons"]}
    assert "LOW_FIT_REQUIRES_ACCEPTANCE" not in codes
    assert "HARD_GAP_REQUIRES_DECISION" in codes


def test_a_requirement_with_no_hard_gap_cannot_be_accepted(api_worker) -> None:
    """A recorded decision about nothing would later read as one about something."""
    application_id = _application(api_worker.services, "Riverside Five", job_text=RIVERSIDE_POSTING)
    outputs = _outputs(_analyze(api_worker, application_id))
    response = _accept(api_worker, application_id, outputs["job_analysis"], ["not-a-requirement"])
    assert response.status_code == 412, response.text
    assert "no hard gap to accept" in response.text


def test_accepting_without_naming_the_plan_is_refused(api_worker) -> None:
    """A decision has to name the plan it was made against.

    Without it the acceptance is applied to whatever plan is active at the
    moment it arrives, which is the silent rebase the field exists to prevent.
    Optional in general, because most submissions accept nothing.
    """
    application_id = _application(
        api_worker.services, "Unnamed Plan Co", job_text=RIVERSIDE_POSTING
    )
    outputs = _outputs(_analyze(api_worker, application_id))
    analysis_id = outputs["job_analysis"]
    hard = _hard_gap_requirement_ids(api_worker, analysis_id)

    refused = api_worker.client.post(
        f"{API_PREFIX}/analyses/{analysis_id}/apply-decisions",
        json={"application_id": application_id, "accepted_requirement_ids": hard[:1]},
        headers=MUTATION_HEADERS,
    )
    assert refused.status_code == 412, refused.text
    assert "expected_selection_plan_id" in refused.text

    # A submission that accepts nothing still does not need it.
    overlay = api_worker.client.post(
        f"{API_PREFIX}/analyses/{analysis_id}/apply-decisions",
        json={
            "application_id": application_id,
            "pinned_fact_ids": [
                api_worker.services.repository.selection_plan(
                    outputs["selection_plan"]
                ).plan.selected_fact_ids[0]
            ],
        },
        headers=MUTATION_HEADERS,
    )
    assert overlay.status_code == 201, overlay.text


def test_naming_a_plan_that_has_been_replaced_is_refused(api_worker) -> None:
    """The decision was made against a plan that is no longer active."""
    application_id = _application(api_worker.services, "Moved Plan Co", job_text=RIVERSIDE_POSTING)
    outputs = _outputs(_analyze(api_worker, application_id))
    analysis_id = outputs["job_analysis"]
    hard = _hard_gap_requirement_ids(api_worker, analysis_id)

    first = _accept(api_worker, application_id, analysis_id, hard[:1])
    assert first.status_code == 201, first.text

    stale = _accept(
        api_worker,
        application_id,
        analysis_id,
        hard[1:],
        expected_selection_plan_id=outputs["selection_plan"],
    )
    assert stale.status_code == 409, stale.text
    assert "moved since this decision was made" in stale.text
