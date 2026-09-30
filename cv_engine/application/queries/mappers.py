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
from ...domain.document import ContentCheck, PreparationState, current_approved_at
from ...domain.drafts import draft_claims
from ...domain.facts import FactStore
from .narrowing import application_is_closed
from .views_prep import (
    BuiltWithView,
    ClaimReviewAssertionView,
    ClaimReviewEvidenceView,
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


def document_facts_view(
    content: DraftDocument | None, facts: FactStore, language: str
) -> list[DraftFactView]:
    """§20: every fact the content links, with the claims that link it."""
    if content is None:
        return []
    linked: dict[str, list[str]] = {}
    section_of: dict[str, str] = {}
    for claim in draft_claims(content):
        for fact_id in claim.fact_ids:
            linked.setdefault(fact_id, []).append(claim.claim_id)
    for section in content.sections:
        for claim in section.claims:
            for fact_id in claim.fact_ids:
                section_of.setdefault(fact_id, section.name)
    return [
        DraftFactView(
            fact_id=fact_id,
            text=_rendering(facts, fact_id, language),
            linked_claim_ids=linked[fact_id],
            section=section_of.get(fact_id),
        )
        for fact_id in sorted(linked)
    ]


def document_view(
    document: CVDocument,
    *,
    language: str,
    facts: FactStore,
    preparation_state: PreparationState,
    content_check: ContentCheck,
) -> DocumentView:
    """Build the public document view field by field, so no stored path can leak."""
    return DocumentView(
        id=document.id,
        application_id=document.application_id,
        analysis_id=document.analysis_id,
        document_hash=document.document_hash,
        built_with=BuiltWithView(profile_version=document.built_with.profile_version),
        language=language,
        content=document.content,
        outline=None if document.content is None else draft_outline_view(document.content),
        facts=document_facts_view(document.content, facts, language),
        preparation_state=preparation_state,
        content_check=content_check,
        content_report=document.content_report,
        approved_at=current_approved_at(document, preparation_state),
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
