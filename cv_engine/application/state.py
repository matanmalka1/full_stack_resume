"""Pure Application state and action-policy projection.

The query service assembles one consistent context.  This module interprets it once:
reasons feed states, and those same values feed actions without a second state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from ..domain.analysis.approval import unresolved_approval_reasons
from ..domain.drafts import render_composite_claim, validate_derived_wording
from ..domain.facts import FactStoreError
from ..domain.knowledge import Knowledge
from ..domain.models import ApprovedRevision, FactStatus, JobAnalysis, SelectionPlan, WorkingDraft
from .queries import (
    ApplicationStateView,
    BlockedActionView,
    PreparationState,
    ReasonView,
    WarningView,
    WorkingDraftState,
)
from .operations import OperationView

STALE_PRECEDENCE = (
    "JOB_SNAPSHOT_CHANGED",
    "ANALYSIS_REPLACED",
    "SELECTION_PLAN_REPLACED",
    "FACT_CHANGED",
    "PROFILE_CHANGED",
    "POLICY_CHANGED",
    "DRAFT_EDITED_AFTER_VALIDATION",
)

PREPARATION_ACTIONS = (
    "analyze",
    "apply_analysis_decisions",
    "create_selection_plan",
    "confirm_and_use_fact",
    "create_draft",
    "update_working_draft",
    "apply_selection_change",
    "regenerate_section",
    "regenerate_claim",
    "archive_working_draft",
    "replace_working_draft",
    "validate",
    "approve",
    "render",
)


@dataclass(frozen=True)
class ProjectionContext:
    application: dict[str, Any]
    active_job_snapshot_id: str
    active_analysis_id: str | None
    active_analysis: JobAnalysis | None
    active_selection_plan: SelectionPlan | None
    draft_selection_plan: SelectionPlan | None
    active_working_draft: WorkingDraft | None
    latest_validation: dict[str, Any] | None
    approved_revisions: tuple[ApprovedRevision, ...]
    ready_revision_ids: frozenset[str]
    knowledge: Knowledge
    today: date
    active_operation: OperationView | None = None


def _reason(
    code: str,
    message: str,
    references: dict[str, str] | None = None,
    actions: list[str] | None = None,
) -> ReasonView:
    return ReasonView(
        code=code,
        message=message,
        entity_references=references or {},
        allowed_resolution_actions=actions or [],
    )


def derive_staleness(context: ProjectionContext) -> list[ReasonView]:
    draft = context.active_working_draft
    if draft is None:
        return []
    reasons: dict[str, ReasonView] = {}

    def add(code: str, message: str, references: dict[str, str] | None = None) -> None:
        reasons[code] = _reason(
            code,
            message,
            references,
            ["replace_working_draft", "archive_working_draft"],
        )

    if draft.source.job_snapshot_id != context.active_job_snapshot_id:
        add(
            "JOB_SNAPSHOT_CHANGED",
            "The active job snapshot changed after this draft was created.",
            {
                "working_draft_id": draft.id,
                "job_snapshot_id": context.active_job_snapshot_id,
            },
        )
    if context.active_analysis_id is not None and draft.job_analysis_id != context.active_analysis_id:
        add(
            "ANALYSIS_REPLACED",
            "A newer analysis replaced the analysis used by this draft.",
            {"working_draft_id": draft.id, "job_analysis_id": context.active_analysis_id},
        )
    active_plan = context.active_selection_plan
    if active_plan is not None and draft.selection_plan_id != active_plan.id:
        add(
            "SELECTION_PLAN_REPLACED",
            "A newer selection plan replaced the plan used by this draft.",
            {"working_draft_id": draft.id, "selection_plan_id": active_plan.id},
        )

    draft_plan = context.draft_selection_plan
    if draft_plan is not None:
        if draft_plan.profile_version != context.knowledge.profiles.version:
            add("PROFILE_CHANGED", "The Profile used by this draft has changed.")
        if draft_plan.selection_policy_version != context.knowledge.policies.version:
            add("POLICY_CHANGED", "The selection policy used by this draft has changed.")

    claims = (
        draft.source.headline,
        *draft.source.contacts,
        *(claim for section in draft.source.sections for claim in section.claims),
    )
    referenced = {fact_id for claim in claims for fact_id in claim.fact_ids}
    replacements = {
        fact.replaces
        for fact in context.knowledge.facts.facts.values()
        if fact.status is FactStatus.CANONICAL and fact.replaces
    }
    fact_dependency_changed = False
    for claim in claims:
        try:
            for fact_id in claim.fact_ids:
                context.knowledge.facts.get(fact_id, canonical_only=True)
            if claim.claim_type == "canonical":
                fact_dependency_changed = claim.text != context.knowledge.facts.rendering(
                    claim.fact_ids[0], draft.source.language
                )
            elif claim.claim_type == "composite":
                fact_dependency_changed = claim.text != render_composite_claim(
                    claim.fact_ids,
                    context.knowledge.facts,
                    draft.source.language,
                    claim.style,
                    claim.template_id or "",
                    claim.template_version or "",
                    context.knowledge.presentations,
                )
            elif claim.claim_type == "derived":
                validate_derived_wording(
                    claim.text,
                    claim.fact_ids,
                    context.knowledge.facts,
                    draft.source.language,
                    claim.style,
                    claim.derivation_id or "",
                    claim.derivation_version or "",
                    context.knowledge.presentations,
                )
        except (FactStoreError, IndexError, ValueError):
            fact_dependency_changed = True
        if fact_dependency_changed:
            break
    if draft_plan is not None and (
        draft_plan.candidate_context_hash != context.knowledge.candidate.version_hash
    ):
        fact_dependency_changed = True
    if fact_dependency_changed or bool(referenced & replacements):
        add("FACT_CHANGED", "A fact used by this draft changed or was superseded.")

    validation = context.latest_validation
    if validation is not None and (
        validation["edit_version"] != draft.edit_version
        or validation["content_hash"] != draft.content_hash
    ):
        add(
            "DRAFT_EDITED_AFTER_VALIDATION",
            "The working draft changed after its latest validation.",
            {"working_draft_id": draft.id},
        )
    return [reasons[code] for code in STALE_PRECEDENCE if code in reasons]


def derive_review_reasons(
    context: ProjectionContext, stale: list[ReasonView]
) -> list[ReasonView]:
    del stale  # Staleness alone is deliberately not a review decision.
    analysis = context.active_analysis
    plan = context.active_selection_plan
    draft = context.active_working_draft
    reasons: list[ReasonView] = []
    if analysis is not None and unresolved_approval_reasons(analysis):
        reasons.append(
            _reason(
                "MATERIAL_CLASSIFICATION_AMBIGUITY",
                "The job classification requires an explicit decision.",
                {"job_analysis_id": context.active_analysis_id or ""},
                ["apply_analysis_decisions"],
            )
        )
    if analysis is not None and analysis.fit.value == "low" and (
        analysis.user_override.get("fit") != "accepted-low-fit"
    ):
        reasons.append(
            _reason(
                "LOW_FIT_REQUIRES_ACCEPTANCE",
                "Low fit requires explicit acceptance before drafting.",
                {"job_analysis_id": context.active_analysis_id or ""},
                ["apply_analysis_decisions"],
            )
        )
    if analysis is not None and any(gap.severity == "hard" for gap in analysis.gaps) and (
        analysis.user_override.get("fit") != "accepted-low-fit"
    ):
        reasons.append(
            _reason(
                "HARD_GAP_REQUIRES_DECISION",
                "A hard requirement gap requires an explicit decision.",
                {"job_analysis_id": context.active_analysis_id or ""},
                ["apply_analysis_decisions"],
            )
        )
    if analysis is not None and plan is None:
        reasons.append(
            _reason(
                "FACT_SELECTION_UNRESOLVED",
                "The active analysis has no active SelectionPlan.",
                {"job_analysis_id": context.active_analysis_id or ""},
                ["create_selection_plan"],
            )
        )
    if draft is not None and any(
        claim.claim_type == "pending"
        for claim in (
            draft.source.headline,
            *draft.source.contacts,
            *(claim for section in draft.source.sections for claim in section.claims),
        )
    ):
        reasons.append(
            _reason(
                "PENDING_FACT_REQUIRES_RESOLUTION",
                "A claim in the active draft depends on a pending fact.",
                {"working_draft_id": draft.id},
                ["confirm_and_use_fact", "update_working_draft"],
            )
        )
    return reasons


def _exact_validation(context: ProjectionContext) -> tuple[bool, bool]:
    draft = context.active_working_draft
    validation = context.latest_validation
    if draft is None or validation is None:
        return False, False
    exact = (
        validation["edit_version"] == draft.edit_version
        and validation["content_hash"] == draft.content_hash
        and validation["job_analysis_id"] == draft.job_analysis_id
        and validation["selection_plan_id"] == draft.selection_plan_id
    )
    return exact, exact and validation["report"].passed


def derive_states(
    context: ProjectionContext,
    stale: list[ReasonView],
    review: list[ReasonView],
) -> tuple[PreparationState, WorkingDraftState]:
    draft = context.active_working_draft
    exact_validation, passing_validation = _exact_validation(context)
    source_stale = any(reason.code != "DRAFT_EDITED_AFTER_VALIDATION" for reason in stale)
    if draft is None:
        draft_state = WorkingDraftState.NONE
    elif source_stale:
        draft_state = WorkingDraftState.STALE
    elif exact_validation and passing_validation:
        draft_state = WorkingDraftState.VALIDATED
    elif exact_validation:
        draft_state = WorkingDraftState.VALIDATION_FAILED
    else:
        draft_state = WorkingDraftState.EDITING

    compatible_analysis = context.active_analysis is not None
    compatible_ready = any(
        revision.id in context.ready_revision_ids
        and revision.job_snapshot_id == context.active_job_snapshot_id
        and revision.job_analysis_id == context.active_analysis_id
        for revision in context.approved_revisions
    )
    compatible_approved = any(
        revision.job_snapshot_id == context.active_job_snapshot_id
        and revision.job_analysis_id == context.active_analysis_id
        for revision in context.approved_revisions
    )
    if not compatible_analysis:
        preparation = PreparationState.NEEDS_ANALYSIS
    elif compatible_ready:
        preparation = PreparationState.READY
    elif compatible_approved:
        preparation = PreparationState.APPROVED
    elif review:
        preparation = PreparationState.NEEDS_REVIEW
    elif source_stale:
        preparation = PreparationState.READY_TO_DRAFT
    elif passing_validation:
        preparation = PreparationState.READY_FOR_APPROVAL
    elif draft is not None:
        preparation = PreparationState.DRAFT_IN_PROGRESS
    else:
        preparation = PreparationState.READY_TO_DRAFT
    return preparation, draft_state


def derive_warnings(context: ProjectionContext, latest_ready: ApprovedRevision | None) -> list[WarningView]:
    warnings: list[WarningView] = []
    if latest_ready is not None and latest_ready.job_snapshot_id != context.active_job_snapshot_id:
        warnings.append(
            WarningView(
                code="READY_REVISION_FOR_OLDER_SNAPSHOT",
                message="The latest Ready revision belongs to an older job snapshot.",
                entity_references={"approved_revision_id": latest_ready.id},
            )
        )
    elif latest_ready is not None and latest_ready.job_analysis_id != context.active_analysis_id:
        warnings.append(
            WarningView(
                code="READY_REVISION_FOR_OLDER_ANALYSIS",
                message="The latest Ready revision belongs to an older analysis.",
                entity_references={"approved_revision_id": latest_ready.id},
            )
        )
    next_date = context.application.get("next_action_date")
    terminal = context.application.get("current_status") in {
        "accepted",
        "rejected",
        "withdrawn",
        "closed",
    }
    if next_date and not terminal:
        try:
            overdue = date.fromisoformat(next_date) < context.today
        except ValueError:
            overdue = False
        if overdue:
            warnings.append(
                WarningView(code="NEXT_ACTION_OVERDUE", message="The next action is overdue.")
            )
    if context.application.get("source") == "migration":
        warnings.append(
            WarningView(
                code="MIGRATED_HISTORICAL",
                message="This Application contains migrated historical records.",
            )
        )
    draft = context.active_working_draft
    if draft is not None:
        referenced = {
            fact_id
            for claim in (
                draft.source.headline,
                *draft.source.contacts,
                *(claim for section in draft.source.sections for claim in section.claims),
            )
            for fact_id in claim.fact_ids
        }
        superseded = sorted(
            fact.fact_id
            for fact in context.knowledge.facts.facts.values()
            if fact.status is FactStatus.CANONICAL
            and fact.replaces is not None
            and fact.replaces in referenced
        )
        if superseded:
            warnings.append(
                WarningView(
                    code="FACT_SUPERSEDED",
                    message="A fact used by the active draft has a canonical replacement.",
                    entity_references={"replacement_fact_id": superseded[0]},
                )
            )
    return warnings


def derive_actions(
    context: ProjectionContext,
    stale: list[ReasonView],
    review: list[ReasonView],
    states: tuple[PreparationState, WorkingDraftState],
) -> tuple[list[str], list[BlockedActionView], str | None]:
    preparation, draft_state = states
    draft = context.active_working_draft
    available: set[str] = {"analyze"}
    for reason in review:
        available.update(reason.allowed_resolution_actions)
    if context.active_analysis is not None and context.active_selection_plan is not None and not review:
        available.add("create_draft")
    if draft is not None:
        available.update({"archive_working_draft", "replace_working_draft"})
        if draft_state is not WorkingDraftState.STALE:
            available.update(
                {
                    "update_working_draft",
                    "apply_selection_change",
                    "regenerate_section",
                    "regenerate_claim",
                    "validate",
                }
            )
    if preparation is PreparationState.READY_FOR_APPROVAL:
        available.add("approve")
    compatible_approved = any(
        revision.job_snapshot_id == context.active_job_snapshot_id
        and revision.job_analysis_id == context.active_analysis_id
        for revision in context.approved_revisions
    )
    if compatible_approved:
        available.add("render")

    blocked: list[BlockedActionView] = []
    review_codes = [reason.code for reason in review]
    stale_codes = [reason.code for reason in stale]
    for action in PREPARATION_ACTIONS:
        if action in available:
            continue
        reasons: list[str]
        if action in {
            "apply_analysis_decisions",
            "create_selection_plan",
            "confirm_and_use_fact",
        }:
            reasons = ["NO_REVIEW_DECISION_REQUIRED"]
        elif action == "create_draft":
            reasons = review_codes or stale_codes or ["ANALYSIS_OR_SELECTION_PLAN_REQUIRED"]
        elif action in {
            "update_working_draft",
            "apply_selection_change",
            "regenerate_section",
            "regenerate_claim",
            "archive_working_draft",
            "replace_working_draft",
            "validate",
        }:
            reasons = stale_codes or ["WORKING_DRAFT_REQUIRED"]
        elif action == "approve":
            if draft_state is WorkingDraftState.VALIDATION_FAILED:
                reasons = ["VALIDATION_FAILED"]
            elif draft_state is WorkingDraftState.EDITING:
                reasons = ["VALIDATION_REQUIRED"]
            else:
                reasons = review_codes or stale_codes or ["VALIDATED_DRAFT_REQUIRED"]
        elif action == "render":
            reasons = ["APPROVED_REVISION_REQUIRED"]
        else:
            reasons = ["ACTION_NOT_AVAILABLE"]
        blocked.append(BlockedActionView(action=action, reasons=list(dict.fromkeys(reasons))))

    recommended = {
        PreparationState.NEEDS_ANALYSIS: "analyze",
        PreparationState.NEEDS_REVIEW: (
            review[0].allowed_resolution_actions[0]
            if review and review[0].allowed_resolution_actions
            else None
        ),
        PreparationState.READY_TO_DRAFT: "create_draft",
        PreparationState.DRAFT_IN_PROGRESS: "validate",
        PreparationState.READY_FOR_APPROVAL: "approve",
        PreparationState.APPROVED: "render",
        PreparationState.READY: None,
    }[preparation]
    if recommended not in available:
        recommended = "replace_working_draft" if "replace_working_draft" in available else None
    return (
        [action for action in PREPARATION_ACTIONS if action in available],
        blocked,
        recommended,
    )


def project_application_state(context: ProjectionContext) -> ApplicationStateView:
    stale = derive_staleness(context)
    review = derive_review_reasons(context, stale)
    states = derive_states(context, stale, review)
    ready = [
        revision
        for revision in context.approved_revisions
        if revision.id in context.ready_revision_ids
    ]
    latest_approved = context.approved_revisions[-1] if context.approved_revisions else None
    latest_ready = ready[-1] if ready else None
    available, blocked, recommended = derive_actions(context, stale, review, states)
    draft = context.active_working_draft
    # Approval atomically deactivates its WorkingDraft. Therefore any active
    # draft observed beside an ApprovedRevision was explicitly created later;
    # timestamps need not be used as an ordering surrogate (they are second-granular).
    newer_draft = draft is not None and latest_approved is not None
    return ApplicationStateView(
        recruitment_status=context.application["current_status"],
        terminal_outcome=context.application.get("terminal_outcome"),
        preparation_state=states[0],
        working_draft_state=states[1],
        review_reasons=review,
        stale_reasons=stale,
        primary_stale_reason=stale[0].code if stale else None,
        warnings=derive_warnings(context, latest_ready),
        active_operation=(
            context.active_operation.model_dump(mode="json")
            if context.active_operation is not None
            else None
        ),
        active_job_snapshot_id=context.active_job_snapshot_id,
        active_analysis_id=context.active_analysis_id,
        active_selection_plan_id=(
            context.active_selection_plan.id if context.active_selection_plan else None
        ),
        active_working_draft_id=draft.id if draft else None,
        latest_approved_revision_id=latest_approved.id if latest_approved else None,
        latest_ready_revision_id=latest_ready.id if latest_ready else None,
        newer_draft_in_progress=newer_draft,
        available_actions=available,
        blocked_actions=blocked,
        recommended_action=recommended,
    )
