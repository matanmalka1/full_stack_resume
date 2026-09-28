"""Pure Application state and action-policy projection (state-and-use-cases.md §4–§9).

The query service captures one consistent read - the Application, its snapshots and
analyses, the CV document, the Operations, and the Knowledge the basis is computed
from. This module interprets it once: the basis feeds the states, the states and the
review reasons feed the actions, and nothing here writes.

`document_review_reasons` is also what the synchronous commands call before they
approve, render or submit, so a blocker the projection shows is the same blocker the
command refuses with.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..domain.contracts.document import CVDocument
from ..domain.contracts.knowledge import FactStatus
from ..domain.document import (
    ContentCheck,
    DocumentState,
    PreparationState,
    basis,
    content_check,
    dependent_fact_ids,
    document_state,
    preparation_state,
)
from ..domain.knowledge import Knowledge
from .operations import OperationType, OperationView
from .queries import ApplicationStateView, BlockedActionView, ReasonView, WarningView

PREPARATION_ACTIONS = (
    "analyze",
    "edit_matching_configuration",
    "build_from_analysis",
    "update_selection",
    "propose_selection",
    "confirm_and_use_fact",
    "create_draft",
    "edit",
    "regenerate_section",
    "regenerate_claim",
    "check",
    "approve",
    "render",
    "submit",
    "download_pdf",
)

#: Commands that change the document. While an Operation that mutates the document
#: is queued or running, none of them is offered (§9).
DOCUMENT_MUTATING_ACTIONS = frozenset(
    {
        "build_from_analysis",
        "update_selection",
        "propose_selection",
        "confirm_and_use_fact",
        "create_draft",
        "edit",
        "regenerate_section",
        "regenerate_claim",
        "check",
        "approve",
        "render",
    }
)

#: Operations that carry `expected_document_hash` and write the document (§11).
DOCUMENT_OPERATION_TYPES = frozenset(
    {
        OperationType.PROPOSE_SELECTION,
        OperationType.CREATE_DRAFT,
        OperationType.REGENERATE_SECTION,
        OperationType.REGENERATE_CLAIM,
        OperationType.RENDER_DOCUMENT,
    }
)

_TERMINAL_RECRUITMENT = frozenset({"accepted", "rejected", "withdrawn", "closed"})


@dataclass(frozen=True)
class ProjectionContext:
    application: dict[str, Any]
    active_job_snapshot_id: str
    #: Every analysis of the Application, oldest first.
    analyses: tuple[dict[str, Any], ...]
    document: CVDocument | None
    knowledge: Knowledge
    today: date
    active_operation: OperationView | None = None
    latest_operation: OperationView | None = None
    matching_context_operation_active: bool = False


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


def document_review_reasons(
    document: CVDocument, knowledge: Knowledge, requested_fact_ids: Iterable[str] = ()
) -> list[ReasonView]:
    """§7 review reasons over the `facts_hash` fact set, plus a requested selection.

    The set is the document's selection united with the facts its claims cite, so a
    fact can never block a document without also being able to change its basis. A
    pending or deleted fact outside it does not affect the Application.
    """
    facts = knowledge.facts.facts
    dependent = set(dependent_fact_ids(document.selection, document.content)) | set(
        requested_fact_ids
    )
    reasons: list[ReasonView] = []
    pending = sorted(
        fact_id
        for fact_id in dependent
        if fact_id in facts and facts[fact_id].status in {FactStatus.PENDING, FactStatus.CONFIRMED}
    )
    if pending:
        reasons.append(
            _reason(
                "PENDING_FACT_REQUIRES_RESOLUTION",
                "The document depends on a fact that is not canonical yet.",
                {"document_id": document.id, "fact_id": pending[0]},
                ["confirm_and_use_fact", "update_selection", "edit"],
            )
        )
    deleted = sorted(
        fact_id
        for fact_id in dependent
        if fact_id in facts and facts[fact_id].status is FactStatus.DELETED
    )
    if deleted:
        reasons.append(
            _reason(
                "FACT_DELETED_REQUIRES_RESOLUTION",
                "The document depends on a fact that has been deleted.",
                {"document_id": document.id, "fact_id": deleted[0]},
                ["update_selection", "edit", "regenerate_section", "regenerate_claim"],
            )
        )
    return reasons


def current_render_error(document: CVDocument | None) -> dict[str, Any] | None:
    """The stored render failure, only while the document is the one that failed (§9).

    A render records the hash it failed against inside the error; once the document
    changes, the failure describes content that no longer exists and is not shown.
    """
    if document is None or document.last_render_error is None:
        return None
    error = document.last_render_error
    if error.get("document_hash") not in {None, document.document_hash}:
        return None
    return error


def _analysis_snapshot(context: ProjectionContext, analysis_id: str) -> str | None:
    return next(
        (row["job_snapshot_id"] for row in context.analyses if row["id"] == analysis_id), None
    )


def derive_warnings(context: ProjectionContext) -> list[WarningView]:
    warnings: list[WarningView] = []
    document = context.document
    knowledge = context.knowledge
    latest = context.analyses[-1] if context.analyses else None
    if document is not None:
        on_older = (latest is not None and latest["id"] != document.analysis_id) or (
            _analysis_snapshot(context, document.analysis_id) != context.active_job_snapshot_id
        )
        if on_older:
            warnings.append(
                WarningView(
                    code="DOCUMENT_ON_OLDER_ANALYSIS",
                    message="The document was built on an older analysis or job snapshot.",
                    entity_references={
                        "document_id": document.id,
                        "job_analysis_id": document.analysis_id,
                    },
                )
            )
        if document.built_with.profile_version != knowledge.profiles.version:
            warnings.append(
                WarningView(
                    code="PROFILE_CHANGED",
                    message="The document was built with an older Profile version.",
                    entity_references={"document_id": document.id},
                )
            )
        if document.built_with.selection_policy_version != knowledge.policies.version:
            warnings.append(
                WarningView(
                    code="POLICY_CHANGED",
                    message="The document was built with an older selection policy.",
                    entity_references={"document_id": document.id},
                )
            )
        dependent = dependent_fact_ids(document.selection, document.content)
        superseded = sorted(
            fact.fact_id
            for fact in knowledge.facts.facts.values()
            if fact.status is FactStatus.CANONICAL
            and fact.replaces is not None
            and fact.replaces in dependent
        )
        if superseded:
            warnings.append(
                WarningView(
                    code="FACT_SUPERSEDED",
                    message="A fact the document uses has a canonical replacement.",
                    entity_references={"replacement_fact_id": superseded[0]},
                )
            )
    next_date = context.application.get("next_action_date")
    if next_date and context.application.get("current_status") not in _TERMINAL_RECRUITMENT:
        try:
            overdue = date.fromisoformat(next_date) < context.today
        except ValueError:
            overdue = False
        if overdue:
            warnings.append(
                WarningView(code="NEXT_ACTION_OVERDUE", message="The next action is overdue.")
            )
    return warnings


def _blocked_reasons(
    action: str,
    context: ProjectionContext,
    *,
    state: DocumentState,
    check: ContentCheck,
    review_codes: list[str],
    document_operation_active: bool,
    analyze_active: bool,
    has_newer_analysis: bool,
) -> list[str]:
    document = context.document
    if context.application.get("deleted_at") is not None:
        return ["APPLICATION_DELETED"]
    if action == "analyze":
        return ["ANALYSIS_IN_PROGRESS"] if analyze_active else ["ANALYSIS_EXISTS"]
    if action == "edit_matching_configuration":
        if not context.analyses:
            return ["ANALYSIS_REQUIRED"]
        return ["MATCHING_CONTEXT_OPERATION_IN_PROGRESS"]
    if document is None:
        return ["DOCUMENT_REQUIRED"]
    if action in DOCUMENT_MUTATING_ACTIONS and document_operation_active:
        return ["DOCUMENT_OPERATION_IN_PROGRESS"]
    if action == "build_from_analysis":
        return [] if has_newer_analysis else ["NO_NEWER_ANALYSIS"]
    if action == "confirm_and_use_fact":
        return ["NO_REVIEW_DECISION_REQUIRED"]
    if action in {"create_draft", "propose_selection"}:
        return ["CONTENT_EXISTS"]
    if action in {"edit", "regenerate_section", "regenerate_claim", "check"}:
        if document.content is None:
            return ["CONTENT_REQUIRED"]
        return ["CONTENT_CHECK_PASSED"]
    if action == "approve":
        if document.content is None:
            return ["CONTENT_REQUIRED"]
        if review_codes:
            return review_codes
        if check is ContentCheck.FAILED:
            return ["VALIDATION_FAILED"]
        return ["DOCUMENT_NOT_DRAFT"]
    if action == "render":
        if state is not DocumentState.APPROVED:
            return (
                ["DOCUMENT_NOT_APPROVED"]
                if state is DocumentState.DRAFT
                else ["DOCUMENT_ALREADY_RENDERED"]
            )
        return review_codes or ["ACTION_NOT_AVAILABLE"]
    if action in {"submit", "download_pdf"}:
        if state is not DocumentState.READY:
            return ["DOCUMENT_NOT_READY"]
        return review_codes or ["ACTION_NOT_AVAILABLE"]
    return ["ACTION_NOT_AVAILABLE"]


def derive_actions(
    context: ProjectionContext,
    review: list[ReasonView],
    state: DocumentState,
    check: ContentCheck,
) -> tuple[list[str], list[BlockedActionView], str | None]:
    document = context.document
    deleted = context.application.get("deleted_at") is not None
    active = context.active_operation
    analyze_active = active is not None and active.operation_type is OperationType.ANALYZE_JOB
    document_operation_active = (
        active is not None and active.operation_type in DOCUMENT_OPERATION_TYPES
    )
    active_snapshot_analysed = any(
        row["job_snapshot_id"] == context.active_job_snapshot_id for row in context.analyses
    )
    latest = context.analyses[-1] if context.analyses else None
    has_newer_analysis = False
    if document is not None and latest is not None and latest["id"] != document.analysis_id:
        versions = {row["id"]: row.get("version_number", 0) for row in context.analyses}
        has_newer_analysis = versions.get(latest["id"], 0) > versions.get(document.analysis_id, 0)
    review_codes = [reason.code for reason in review]

    available: set[str] = set()
    if not deleted:
        if not active_snapshot_analysed and not analyze_active:
            available.add("analyze")
        if context.analyses and not context.matching_context_operation_active:
            available.add("edit_matching_configuration")
        if document is not None:
            has_content = document.content is not None
            candidates = {"update_selection"}
            if has_newer_analysis:
                candidates.add("build_from_analysis")
            if not has_content:
                candidates.update({"create_draft", "propose_selection"})
            else:
                candidates.update({"edit", "regenerate_section", "regenerate_claim"})
                if check is not ContentCheck.PASSED:
                    candidates.add("check")
                if state is DocumentState.DRAFT and not review and check is not ContentCheck.FAILED:
                    candidates.add("approve")
            if state is DocumentState.APPROVED and not review:
                candidates.add("render")
            if state is DocumentState.READY and not review:
                candidates.add("submit")
            for reason in review:
                candidates.update(
                    action
                    for action in reason.allowed_resolution_actions
                    if action in PREPARATION_ACTIONS and (action not in {"edit"} or has_content)
                )
            if document_operation_active:
                candidates -= DOCUMENT_MUTATING_ACTIONS
            available |= candidates
        if state is DocumentState.READY:
            available.add("download_pdf")

    blocked = [
        BlockedActionView(
            action=action,
            reasons=list(
                dict.fromkeys(
                    _blocked_reasons(
                        action,
                        context,
                        state=state,
                        check=check,
                        review_codes=review_codes,
                        document_operation_active=document_operation_active,
                        analyze_active=analyze_active,
                        has_newer_analysis=has_newer_analysis,
                    )
                )
            ),
        )
        for action in PREPARATION_ACTIONS
        if action not in available
    ]

    # §9 recommendation order, first match wins.
    recommended: str | None = None
    if document is None:
        recommended = "analyze"
    elif document.content is None:
        recommended = "create_draft"
    elif check in {ContentCheck.NONE, ContentCheck.OUTDATED}:
        recommended = "check"
    else:
        recommended = next(
            (action for action in ("approve", "render", "submit") if action in available), None
        )
    if recommended not in available:
        recommended = None
    return [action for action in PREPARATION_ACTIONS if action in available], blocked, recommended


def project_application_state(context: ProjectionContext) -> ApplicationStateView:
    document = context.document
    current_basis = basis(document, context.knowledge.facts.facts) if document is not None else None
    state = document_state(document, current_basis)
    check = content_check(document, current_basis)
    preparation: PreparationState = preparation_state(document, current_basis)
    review = document_review_reasons(document, context.knowledge) if document is not None else []
    available, blocked, recommended = derive_actions(context, review, state, check)
    latest = context.analyses[-1] if context.analyses else None
    return ApplicationStateView(
        recruitment_status=context.application["current_status"],
        terminal_outcome=context.application.get("terminal_outcome"),
        preparation_state=preparation,
        document_state=state,
        content_check=check,
        review_reasons=review,
        warnings=derive_warnings(context),
        active_operation=context.active_operation,
        latest_operation=context.latest_operation,
        active_job_snapshot_id=context.active_job_snapshot_id,
        latest_analysis_id=latest["id"] if latest is not None else None,
        document_id=document.id if document is not None else None,
        document_hash=document.document_hash if document is not None else None,
        document_analysis_id=document.analysis_id if document is not None else None,
        approved_at=document.approved_at if document is not None else None,
        last_render_error=current_render_error(document),
        available_actions=available,
        blocked_actions=blocked,
        recommended_action=recommended,
    )
