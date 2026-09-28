"""Mappers from domain and repository records to application query DTOs."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ...domain.analysis.projection import fit_level, fit_score
from ...domain.analysis.projection import gaps as project_gaps
from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.document import CVDocument, DocumentSubmission
from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.selection import SelectionManifest
from ...domain.document import ContentCheck, DocumentState, current_approved_at
from ...domain.drafts import draft_claims
from ...domain.facts import FactStore
from ...domain.selection import ROLE_BLOCK_TAG, STRUCTURAL_STYLES
from .narrowing import application_is_closed
from .views_prep import (
    ArtifactVersionView,
    BuiltWithView,
    ClaimReviewAssertionView,
    ClaimReviewEvidenceView,
    DocumentCandidateView,
    DocumentSelectionView,
    DocumentView,
    DraftClaimView,
    DraftFactView,
    DraftOutlineView,
    DraftSectionView,
    JobAnalysisView,
    JobSnapshotView,
)
from .views_shared import ApplicationListItemView, ApplicationStateView, ApplicationView
from .views_tracking import RecruitmentTimelineItemView, SubmissionView


def _fit_projection(analysis: JobAnalysis | None) -> dict[str, Any]:
    """Fit as the requirements make it, for a record that no longer stores it."""
    if analysis is None:
        return {"fit_level": None, "fit_score": None}
    return {
        "fit_level": fit_level(analysis.requirements).value,
        "fit_score": fit_score(analysis.requirements),
    }


def application_view(
    record: dict[str, Any], analysis: JobAnalysis | None = None
) -> ApplicationView:
    return ApplicationView.model_validate({**record, **_fit_projection(analysis)})


def _claim_view(claim: Any) -> DraftClaimView:
    review_evidence = None
    if claim.review_evidence is not None:
        review_evidence = ClaimReviewEvidenceView(
            policy_version=claim.review_evidence.policy_version,
            assertions=[
                ClaimReviewAssertionView(
                    claim_quote=assertion.claim_quote,
                    fact_ids=list(assertion.fact_ids),
                    source_quotes=list(assertion.source_quotes),
                )
                for assertion in claim.review_evidence.assertions
            ],
        )
    return DraftClaimView(
        claim_id=claim.claim_id,
        style=claim.style,
        text=claim.text,
        claim_type=claim.claim_type,
        fact_ids=list(claim.fact_ids),
        pending_reason=claim.pending_reason,
        review_evidence=review_evidence,
    )


def draft_outline_view(draft: DraftDocument) -> DraftOutlineView:
    """Build the editable outline from the draft rather than storing a second copy."""
    return DraftOutlineView(
        headline=_claim_view(draft.headline),
        contacts=[_claim_view(claim) for claim in draft.contacts],
        sections=[
            DraftSectionView(
                name=section.name,
                claims=[_claim_view(claim) for claim in section.claims],
            )
            for section in draft.sections
        ],
    )


def _rendering(facts: FactStore, fact_id: str, language: str) -> str | None:
    try:
        return facts.rendering(fact_id, language)
    except (KeyError, ValueError):
        return None


def document_selection_view(
    selection: SelectionManifest, facts: FactStore, language: str
) -> DocumentSelectionView:
    """Pair the selection's ranking with readable current canonical fact renderings.

    A fact that no longer resolves is shown without text and is not selectable,
    rather than turning the read into a technical failure.
    """
    candidates: list[DocumentCandidateView] = []
    for candidate in selection.candidates:
        try:
            fact = facts.get(candidate.fact_id, canonical_only=True)
            text = facts.rendering(candidate.fact_id, language)
            user_selectable = (
                fact.resume_style not in STRUCTURAL_STYLES and ROLE_BLOCK_TAG not in fact.tags
            )
        except (KeyError, ValueError):
            text = None
            user_selectable = False
        candidates.append(
            DocumentCandidateView(
                fact_id=candidate.fact_id,
                text=text,
                section=candidate.section,
                outcome=candidate.outcome,
                reason=candidate.reason,
                user_selectable=user_selectable,
            )
        )
    return DocumentSelectionView(
        emphasis=selection.emphasis,
        emphasis_override=selection.emphasis_override,
        selected_fact_ids=list(selection.selected_fact_ids),
        pinned_fact_ids=list(selection.pinned_fact_ids),
        excluded_fact_ids=list(selection.excluded_fact_ids),
        proposed_by=selection.proposed_by,
        proposal_rationale=selection.proposal_rationale,
        candidates=candidates,
    )


def document_facts_view(
    selection: SelectionManifest, content: DraftDocument | None, facts: FactStore, language: str
) -> list[DraftFactView]:
    """§20 candidate accounting: every fact the content links, and every candidate.

    The union of the two, because neither covers the other. Contacts come from the
    candidate context and never appear in a selection, while an omitted candidate
    appears in no claim.
    """
    linked: dict[str, list[str]] = {}
    if content is not None:
        for claim in draft_claims(content):
            for fact_id in claim.fact_ids:
                linked.setdefault(fact_id, []).append(claim.claim_id)
    candidates = {candidate.fact_id: candidate for candidate in selection.candidates}
    return [
        DraftFactView(
            fact_id=fact_id,
            text=_rendering(facts, fact_id, language),
            linked_claim_ids=linked.get(fact_id, []),
            section=candidates[fact_id].section if fact_id in candidates else None,
            outcome=candidates[fact_id].outcome if fact_id in candidates else None,
            reason=candidates[fact_id].reason if fact_id in candidates else None,
        )
        for fact_id in sorted(set(linked) | set(candidates))
    ]


def document_view(
    document: CVDocument,
    *,
    language: str,
    facts: FactStore,
    document_state: DocumentState,
    content_check: ContentCheck,
) -> DocumentView:
    """Build the public document view field by field, so no stored path can leak."""
    return DocumentView(
        id=document.id,
        application_id=document.application_id,
        analysis_id=document.analysis_id,
        document_hash=document.document_hash,
        built_with=BuiltWithView(
            profile_version=document.built_with.profile_version,
            selection_policy_version=document.built_with.selection_policy_version,
        ),
        language=language,
        selection=document_selection_view(document.selection, facts, language),
        content=document.content,
        outline=None if document.content is None else draft_outline_view(document.content),
        facts=document_facts_view(document.selection, document.content, facts, language),
        document_state=document_state,
        content_check=content_check,
        content_report=document.content_report,
        approved_at=current_approved_at(document, document_state),
        last_render_error=document.last_render_error,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def submission_view(submission: DocumentSubmission) -> SubmissionView:
    """What was sent, with each file's checksum and never its stored location."""
    return SubmissionView(
        id=submission.id,
        application_id=submission.application_id,
        submission_type=submission.submission_type,
        submitted_at=submission.submitted_at,
        job_snapshot_id=submission.job_snapshot_id,
        document_hash=submission.document_hash,
        content=submission.content,
        html_sha256=submission.html_sha256,
        pdf_sha256=submission.pdf_sha256,
        metadata=submission.metadata,
    )


def application_list_item_view(
    record: dict[str, Any], state: ApplicationStateView, analysis: JobAnalysis | None = None
) -> ApplicationListItemView:
    return ApplicationListItemView.model_validate(
        {
            **record,
            **state.model_dump(mode="python"),
            **_fit_projection(analysis),
            "is_closed": application_is_closed(state.terminal_outcome, state.recruitment_status),
        }
    )


def recruitment_timeline_view(
    events: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
    audits: list[dict[str, Any]],
) -> list[RecruitmentTimelineItemView]:
    """Merge append-only tracking records into one deterministic presentation trail."""
    submission_audits = {
        row["entity_id"]: row for row in audits if row.get("entity_type") == "submission"
    }
    items: list[RecruitmentTimelineItemView] = []
    for row in events:
        payload = json.loads(row.get("payload_json") or "{}")
        items.append(
            RecruitmentTimelineItemView(
                id=row["id"],
                item_type=row["event_type"],
                occurred_at=row["occurred_at"],
                actor_type=row.get("actor_type"),
                client=row.get("client"),
                from_status=row.get("from_status"),
                to_status=row.get("to_status"),
                corrects_event_id=row.get("corrects_event_id"),
                reason=row.get("reason") or "",
                next_action=payload.get("next_action"),
                next_action_date=payload.get("next_action_date"),
            )
        )
    for row in submissions:
        audit = submission_audits.get(row["id"], {})
        items.append(
            RecruitmentTimelineItemView(
                id=row["id"],
                item_type="submission",
                occurred_at=row["submitted_at"],
                actor_type=audit.get("actor_type"),
                client=audit.get("client"),
                submission_type=row["submission_type"],
                document_hash=row.get("document_hash"),
                metadata=json.loads(row.get("metadata_json") or "{}"),
            )
        )
    priority = {
        "submission": 0,
        "status_transition": 1,
        "status_correction": 2,
        "next_action": 3,
    }
    return sorted(
        items,
        key=lambda item: (item.occurred_at, priority.get(item.item_type, 9), item.id),
    )


def snapshot_view(record: dict[str, Any], job_text: str) -> JobSnapshotView:
    return JobSnapshotView.model_validate(
        {
            **{
                key: record.get(key)
                for key in JobSnapshotView.model_fields
                if key not in {"source_metadata", "job_text"}
            },
            "job_text": job_text,
            "source_metadata": json.loads(record.get("source_metadata_json") or "{}"),
            "source_hash": record["source_hash"],
        }
    )


def analysis_view(record: dict[str, Any], facts: FactStore) -> JobAnalysisView:
    analysis: JobAnalysis = record["analysis"]
    projected = {"fit_level", "fit_score", "gaps", "analysis"}
    return JobAnalysisView.model_validate(
        {
            **{
                key: record.get(key) for key in JobAnalysisView.model_fields if key not in projected
            },
            "analysis": analysis,
            "fit_level": fit_level(analysis.requirements).value,
            "fit_score": fit_score(analysis.requirements),
            "gaps": [asdict(gap) for gap in project_gaps(analysis.requirements, facts)],
        }
    )


def artifact_version_view(record: dict[str, Any]) -> ArtifactVersionView:
    return ArtifactVersionView.model_validate(
        {
            **{
                key: record.get(key)
                for key in ArtifactVersionView.model_fields
                if key != "metadata"
            },
            "metadata": json.loads(record.get("metadata_json") or "{}"),
        }
    )
