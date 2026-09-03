from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB, approve_active_draft
from sqlalchemy import update

from cv_engine.application.commands import (
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    DraftCommand,
    IngestCommand,
)
from cv_engine.application.queries import PreparationState, WorkingDraftState
from cv_engine.application.state import ProjectionContext, derive_review_reasons
from cv_engine.domain.analysis.approval import (
    ACCEPTED_INCOMPLETE_ANALYSIS,
    ANALYSIS_INCOMPLETE,
    APPROVAL_REASONS,
    CLASSIFICATION_AMBIGUITY,
)
from cv_engine.domain.facts import FactStore
from cv_engine.domain.knowledge import Knowledge
from cv_engine.domain.models import (
    FitLevel,
    JobAnalysis,
    ValidationIssue,
    ValidationReport,
    ValidationRunLineage,
)
from cv_engine.infrastructure.persistence.tables import applications
from cv_engine.util import new_id, sha256_text


def test_application_projection_follows_the_preparation_lifecycle(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="State Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.preparation_state is PreparationState.NEEDS_ANALYSIS
    assert detail.working_draft_state is WorkingDraftState.NONE
    assert detail.active_job_snapshot_id == ingested.job_snapshot_id
    assert detail.recommended_action == "analyze"
    listed = services.queries.list_applications().items[0]
    assert listed.id == ingested.application_id
    assert listed.preparation_state is PreparationState.NEEDS_ANALYSIS

    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.preparation_state is PreparationState.READY_TO_DRAFT
    assert detail.active_analysis_id == analysed.analysis_id
    assert detail.active_selection_plan_id == analysed.selection_plan_id
    assert detail.recommended_action == "create_draft"

    drafted = services.drafts.draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )
    )
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.preparation_state is PreparationState.READY_FOR_APPROVAL
    assert detail.working_draft_state is WorkingDraftState.VALIDATED
    assert detail.active_working_draft_id == drafted.working_draft_id
    assert detail.recommended_action == "approve"
    assert "approve" in detail.available_actions

    approved = approve_active_draft(services, ingested.application_id)
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.preparation_state is PreparationState.APPROVED
    assert detail.working_draft_state is WorkingDraftState.NONE
    assert detail.latest_approved_revision_id == approved.revision_id
    assert detail.recommended_action == "render"


def test_material_ambiguity_is_a_review_reason_and_blocks_drafting(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Ambiguous State Co",
            target_role="Sales",
            job_text=AMBIGUOUS_HEBREW_JOB,
            client="web",
        )
    )
    services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )

    detail = services.queries.application_detail(ingested.application_id)
    assert detail.preparation_state is PreparationState.NEEDS_REVIEW
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" in {reason.code for reason in detail.review_reasons}
    blocked = {item.action: item.reasons for item in detail.blocked_actions}
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" in blocked["create_draft"]
    assert detail.recommended_action == "apply_analysis_decisions"


#: Requirements stated in prose that neither the concept vocabulary nor the
#: legacy gap rules can read. The engine's honest answer is that it did not
#: understand this posting - which is a blocker no decision settles.
UNREADABLE_POSTING = (
    "Account Executive.\n"
    "You have experience closing complex B2B deals, understand enterprise "
    "procurement, and negotiate with senior stakeholders.\n"
)


@pytest.fixture
def knowledge(
    fact_store,
    profile_store,
    policy_store,
    candidate_context,
    presentation_store,
    requirement_concepts,
) -> Knowledge:
    """The knowledge surface a projection runs against, without a database."""
    return Knowledge(
        facts=fact_store,
        profiles=profile_store,
        policies=policy_store,
        candidate=candidate_context,
        presentations=presentation_store,
        requirement_concepts=requirement_concepts,
    )


def _reasons_for(knowledge: Knowledge, analysis: JobAnalysis) -> dict[str, list[str]]:
    """The review reasons an analysis alone projects, and what each advertises.

    `derive_review_reasons` is pure, so the analysis is handed to it directly.
    Reaching it through ingest and analyze would test which reasons the
    classifier produces rather than what the projection does with them.
    """
    context = ProjectionContext(
        application={"current_status": "saved"},
        active_job_snapshot_id="snapshot",
        active_analysis_id="analysis",
        active_analysis=analysis,
        active_selection_plan=None,
        draft_selection_plan=None,
        active_working_draft=None,
        latest_validation=None,
        approved_revisions=(),
        ready_revision_ids=frozenset(),
        knowledge=knowledge,
        today=date.today(),
    )
    return {
        reason.code: reason.allowed_resolution_actions
        for reason in derive_review_reasons(context, [])
    }


def _analysis_needing(reason: str) -> JobAnalysis:
    return JobAnalysis.model_validate(
        {
            "track": "sales",
            "profile": "account-executive",
            "emphasis": "new-business",
            "confidence": 0.4,
            "rationale": "projection fixture",
            "fit": "unknown",
            "gaps": [],
            "mandatory_requirements": [],
            "preferred_requirements": [],
            "keywords": [],
            "language": "en",
            "classification_requires_approval": True,
            "approval_reasons": [reason],
        }
    )


@pytest.mark.parametrize(
    "reason",
    sorted(
        name
        for name, entry in APPROVAL_REASONS.items()
        if entry.review_code == CLASSIFICATION_AMBIGUITY
    ),
)
def test_a_classification_reason_is_offered_the_command_that_decides_it(knowledge, reason) -> None:
    """Derived from the table, so a reason cannot change kind without saying so."""
    reasons = _reasons_for(knowledge, _analysis_needing(reason))
    assert reasons[CLASSIFICATION_AMBIGUITY] == ["apply_analysis_decisions"]
    assert ANALYSIS_INCOMPLETE not in reasons


def test_extraction_failure_is_its_own_reason_with_its_own_decision(knowledge) -> None:
    """It blocks, it is not a classification ambiguity, and it has a way out.

    It was projected as `MATERIAL_CLASSIFICATION_AMBIGUITY` offering
    `apply_analysis_decisions`, which committed, returned success and left the
    same blocker standing - naming a Track recovers nothing. Reporting it with
    no action at all was honest but left a blocked state with no exit, which is
    not a review reason either.
    """
    reasons = _reasons_for(knowledge, _analysis_needing("extraction-failed"))
    assert reasons[ANALYSIS_INCOMPLETE] == ["apply_analysis_decisions"]
    assert CLASSIFICATION_AMBIGUITY not in reasons


def test_an_unregistered_reason_blocks_and_advertises_nothing(knowledge) -> None:
    """Fail closed, so the guard is the only thing that has to be right.

    A reason the table does not know cannot be said to be resolvable by
    anything, and must not be silently dropped either. It blocks with no
    action, and grouping it beside a reason that *is* resolvable takes the
    intersection - so the resolvable one's command is not advertised as
    settling what it cannot.
    """
    reasons = _reasons_for(knowledge, _analysis_needing("brand-new-reason"))
    assert reasons[ANALYSIS_INCOMPLETE] == []

    analysis = _analysis_needing("extraction-failed")
    both = JobAnalysis.model_validate(
        {
            **analysis.model_dump(mode="json"),
            "approval_reasons": ["extraction-failed", "brand-new-reason"],
        }
    )
    assert _reasons_for(knowledge, both)[ANALYSIS_INCOMPLETE] == []


def test_an_unreadable_posting_stays_blocked_after_the_classification_is_decided(
    services,
) -> None:
    """The decidable half is offered once, taken, and does not come back.

    Both reasons stand at first, because a posting that could not be read also
    scores no confidence, and "what is this job?" is a different question from
    "proceed although nothing was read?". Each is reported on its own terms and
    each is answered separately: after the classification decision the analysis
    is still incomplete, and the acceptance is what settles that.
    """
    ingested = services.applications.ingest(
        IngestCommand(
            company="Unreadable Posting Co",
            target_role="Account Executive",
            job_text=UNREADABLE_POSTING,
            client="web",
        )
    )
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    detail = services.queries.application_detail(ingested.application_id)
    assert detail.preparation_state is PreparationState.NEEDS_REVIEW
    offered = {reason.code: reason.allowed_resolution_actions for reason in detail.review_reasons}
    # Two reasons, two decisions, each advertising the command that takes it.
    assert offered[ANALYSIS_INCOMPLETE] == ["apply_analysis_decisions"]
    assert offered[CLASSIFICATION_AMBIGUITY] == ["apply_analysis_decisions"]

    services.analysis.apply_analysis_decisions(
        ApplyAnalysisDecisionsCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            track_override="sales",
            profile_override="account-executive",
        )
    )

    after = services.queries.application_detail(ingested.application_id)
    offered = {reason.code: reason.allowed_resolution_actions for reason in after.review_reasons}
    assert CLASSIFICATION_AMBIGUITY not in offered
    assert offered[ANALYSIS_INCOMPLETE] == ["apply_analysis_decisions"]
    assert after.preparation_state is PreparationState.NEEDS_REVIEW
    blocked = {item.action: item.reasons for item in after.blocked_actions}
    assert ANALYSIS_INCOMPLETE in blocked["create_draft"]

    # The decision that does answer it, and what it leaves standing.
    accepted = services.analysis.apply_analysis_decisions(
        ApplyAnalysisDecisionsCommand(
            application_id=ingested.application_id,
            job_analysis_id=after.active_analysis_id or "",
            accept_incomplete_analysis=True,
        )
    )
    settled = services.queries.application_detail(ingested.application_id)
    assert ANALYSIS_INCOMPLETE not in {reason.code for reason in settled.review_reasons}
    assert settled.preparation_state is PreparationState.READY_TO_DRAFT
    # Accepted, not understood: the analysis still reports it read nothing.
    assert accepted.analysis.fit is FitLevel.UNKNOWN
    assert "extraction-failed" in accepted.analysis.approval_reasons
    assert accepted.analysis.user_override["analysis"] == ACCEPTED_INCOMPLETE_ANALYSIS


def test_ready_milestone_survives_a_new_draft_for_the_same_context(ready_application) -> None:
    setup = ready_application("Parallel Draft State Co")
    before = setup.services.queries.application_detail(setup.application_id)
    assert before.preparation_state is PreparationState.READY
    assert before.latest_ready_revision_id == setup.approved.revision_id
    assert before.newer_draft_in_progress is False

    setup.services.drafts.draft(
        DraftCommand(
            application_id=setup.application_id,
            job_analysis_id=setup.analysis_id,
            selection_plan_id=setup.selection_plan_id,
        )
    )
    after = setup.services.queries.application_detail(setup.application_id)
    assert after.preparation_state is PreparationState.READY
    assert after.working_draft_state is WorkingDraftState.VALIDATED
    assert after.latest_ready_revision_id == setup.approved.revision_id
    assert after.newer_draft_in_progress is True


def test_new_snapshot_makes_ready_historical_and_requires_analysis(ready_application) -> None:
    setup = ready_application("Historical Ready State Co")
    snapshot_id = new_id()
    text = "A changed Account Manager role with a new territory."
    payload = setup.services.payloads.commit_snapshot(setup.application_id, snapshot_id, text)
    setup.services.repository.add_job_snapshot(
        setup.application_id,
        payload.reference,
        payload.sha256,
        sha256_text(text.lower()),
        snapshot_id=snapshot_id,
    )

    detail = setup.services.queries.application_detail(setup.application_id)
    assert detail.preparation_state is PreparationState.NEEDS_ANALYSIS
    assert detail.latest_ready_revision_id == setup.approved.revision_id
    assert detail.active_analysis_id is None
    assert {warning.code for warning in detail.warnings} == {"READY_REVISION_FOR_OLDER_SNAPSHOT"}


def test_new_analysis_makes_parallel_draft_stale_without_erasing_ready_history(
    ready_application,
) -> None:
    setup = ready_application("Historical Analysis State Co")
    setup.services.drafts.draft(
        DraftCommand(
            application_id=setup.application_id,
            job_analysis_id=setup.analysis_id,
            selection_plan_id=setup.selection_plan_id,
        )
    )
    replacement = setup.services.analysis.analyze(
        AnalyzeCommand(
            application_id=setup.application_id,
            job_snapshot_id=setup.snapshot_id,
        )
    )

    detail = setup.services.queries.application_detail(setup.application_id)
    assert detail.preparation_state is PreparationState.READY_TO_DRAFT
    assert detail.working_draft_state is WorkingDraftState.STALE
    assert detail.active_analysis_id == replacement.analysis_id
    assert [reason.code for reason in detail.stale_reasons[:2]] == [
        "ANALYSIS_REPLACED",
        "SELECTION_PLAN_REPLACED",
    ]
    assert detail.latest_ready_revision_id == setup.approved.revision_id
    assert {warning.code for warning in detail.warnings} == {"READY_REVISION_FOR_OLDER_ANALYSIS"}


def test_failed_exact_validation_drives_state_and_approve_blocker(drafted_application) -> None:
    setup = drafted_application("Failed Validation State Co")
    working = setup.services.repository.active_working_draft(setup.application_id)
    analysis = setup.services.repository.get_analysis(setup.analysis_id)
    knowledge = setup.services.knowledge.load()
    setup.services.repository.record_validation(
        setup.application_id,
        "pre-render",
        ValidationReport.from_findings(
            groups={"content": False},
            issues=[ValidationIssue(group="content", code="test-failure", message="failed")],
        ),
        lineage=ValidationRunLineage(
            working_draft_id=working.id,
            edit_version=working.edit_version,
            content_hash=working.content_hash,
            job_snapshot_id=analysis["job_snapshot_id"],
            job_analysis_id=working.job_analysis_id,
            selection_plan_id=working.selection_plan_id,
            knowledge_context_hash=knowledge.document_context_hash(),
            validator_versions={"test": "1"},
        ),
    )

    detail = setup.services.queries.application_detail(setup.application_id)
    assert detail.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert detail.working_draft_state is WorkingDraftState.VALIDATION_FAILED
    blocked = {item.action: item.reasons for item in detail.blocked_actions}
    assert blocked["approve"] == ["VALIDATION_FAILED"]


def test_edit_after_validation_is_a_reason_but_not_source_staleness(drafted_application) -> None:
    setup = drafted_application("Edited Validation State Co")
    working = setup.services.repository.active_working_draft(setup.application_id)
    edited_source = working.source.model_copy(update={"content_hash": "edited-content"})
    setup.services.repository.update_working_draft(
        working.id,
        working.edit_version,
        edited_source,
    )

    detail = setup.services.queries.application_detail(setup.application_id)
    assert detail.preparation_state is PreparationState.DRAFT_IN_PROGRESS
    assert detail.working_draft_state is WorkingDraftState.EDITING
    assert detail.primary_stale_reason == "DRAFT_EDITED_AFTER_VALIDATION"
    assert detail.recommended_action == "validate"


def test_profile_and_policy_versions_are_source_stale_reasons(
    drafted_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = drafted_application("Knowledge Policy State Co")
    changed = setup.services.knowledge.load()
    changed.profiles.version = "changed-profile-version"
    changed.policies.version = "changed-policy-version"
    monkeypatch.setattr(setup.services.knowledge, "load", lambda: changed)

    detail = setup.services.queries.application_detail(setup.application_id)
    assert detail.working_draft_state is WorkingDraftState.STALE
    assert {reason.code for reason in detail.stale_reasons} >= {
        "PROFILE_CHANGED",
        "POLICY_CHANGED",
    }


def test_unrelated_canonical_fact_change_does_not_stale_the_draft(
    drafted_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = drafted_application("Unrelated Fact State Co")
    knowledge = setup.services.knowledge.load()
    working = setup.services.repository.active_working_draft(setup.application_id)
    referenced = {
        fact_id
        for claim in (
            working.source.headline,
            *working.source.contacts,
            *(claim for section in working.source.sections for claim in section.claims),
        )
        for fact_id in claim.fact_ids
    }
    unrelated_id = next(fact_id for fact_id in knowledge.facts.facts if fact_id not in referenced)
    facts = dict(knowledge.facts.facts)
    facts[unrelated_id] = facts[unrelated_id].model_copy(
        update={"meaning": f"{facts[unrelated_id].meaning} (changed)"}
    )
    changed_facts = FactStore(facts, dict(knowledge.facts.source_versions))
    assert changed_facts.version != knowledge.facts.version
    changed = replace(knowledge, facts=changed_facts)
    monkeypatch.setattr(setup.services.knowledge, "load", lambda: changed)

    detail = setup.services.queries.application_detail(setup.application_id)
    assert "FACT_CHANGED" not in {reason.code for reason in detail.stale_reasons}
    assert detail.working_draft_state is WorkingDraftState.VALIDATED


def test_pending_claim_recommends_its_resolution_action(drafted_application) -> None:
    setup = drafted_application("Pending Review State Co")
    working = setup.services.repository.active_working_draft(setup.application_id)
    section = working.source.sections[0]
    claim = section.claims[0]
    pending = claim.model_copy(
        update={
            "text": "An unsupported manual statement.",
            "text_hash": sha256_text("An unsupported manual statement."),
            "fact_ids": [],
            "claim_type": "pending",
            "pending_reason": "manual wording has no canonical support",
        }
    )
    changed_section = section.model_copy(update={"claims": [pending, *section.claims[1:]]})
    changed_source = working.source.model_copy(
        update={
            "sections": [changed_section, *working.source.sections[1:]],
            "content_hash": "pending-content",
        }
    )
    setup.services.repository.update_working_draft(
        working.id,
        working.edit_version,
        changed_source,
    )

    detail = setup.services.queries.application_detail(setup.application_id)
    assert detail.preparation_state is PreparationState.NEEDS_REVIEW
    assert {reason.code for reason in detail.review_reasons} == {"PENDING_FACT_REQUIRES_RESOLUTION"}
    assert detail.recommended_action == "confirm_and_use_fact"
    assert "confirm_and_use_fact" in detail.available_actions


def test_projection_queries_share_one_database_snapshot(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Snapshot Co", target_role="Developer", job_text="Python role", client="web"
        )
    )
    repository = services.repository
    with repository.read_transaction() as reader:
        before = reader.get_application(ingested.application_id)
        with repository.engine.begin() as writer:
            writer.execute(
                update(applications)
                .where(applications.c.id == ingested.application_id)
                .values(next_action="Call recruiter")
            )
        during = reader.get_application(ingested.application_id)

    after = repository.get_application(ingested.application_id)
    assert before["next_action"] is None
    assert during["next_action"] is None
    assert after["next_action"] == "Call recruiter"
