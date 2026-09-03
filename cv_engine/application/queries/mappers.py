"""Mappers from domain and repository records to application query DTOs."""

from __future__ import annotations

import json
from typing import Any

from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.records import ApprovedRevision
from ...domain.drafts import draft_claims
from ...domain.facts import FactStore
from .narrowing import application_is_closed
from .views import (
    ApplicationListItemView,
    ApplicationStateView,
    ApplicationView,
    ApprovedRevisionView,
    ArtifactVersionView,
    DecisionRecordView,
    DraftClaimView,
    DraftFactView,
    DraftOutlineView,
    DraftSectionView,
    JobAnalysisView,
    JobSnapshotView,
    RecruitmentTimelineItemView,
    WorkingDraftFactsView,
)


def application_view(record: dict[str, Any]) -> ApplicationView:
    return ApplicationView.model_validate(record)


def _claim_view(claim: Any) -> DraftClaimView:
    return DraftClaimView(
        claim_id=claim.claim_id,
        style=claim.style,
        text=claim.text,
        claim_type=claim.claim_type,
        fact_ids=list(claim.fact_ids),
        pending_reason=claim.pending_reason,
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


def draft_facts_view(
    working_draft_id: str,
    application_id: str,
    selection_plan_id: str,
    draft: DraftDocument,
    facts: FactStore,
) -> WorkingDraftFactsView:
    """Return every linked fact and every candidate this draft considered.

    Missing fact renderings remain a readable stale state instead of turning the
    editor query into a technical failure.
    """
    linked: dict[str, list[str]] = {}
    for claim in draft_claims(draft):
        for fact_id in claim.fact_ids:
            linked.setdefault(fact_id, []).append(claim.claim_id)

    candidates = {
        candidate.fact_id: candidate
        for candidate in (draft.selection.candidates if draft.selection is not None else [])
    }

    def rendering(fact_id: str) -> str | None:
        try:
            return facts.rendering(fact_id, draft.language)
        except (KeyError, ValueError):
            return None

    return WorkingDraftFactsView(
        working_draft_id=working_draft_id,
        application_id=application_id,
        selection_plan_id=selection_plan_id,
        language=draft.language,
        facts=[
            DraftFactView(
                fact_id=fact_id,
                text=rendering(fact_id),
                linked_claim_ids=linked.get(fact_id, []),
                section=candidates[fact_id].section if fact_id in candidates else None,
                outcome=candidates[fact_id].outcome if fact_id in candidates else None,
                reason=candidates[fact_id].reason if fact_id in candidates else None,
            )
            for fact_id in sorted(set(linked) | set(candidates))
        ],
    )


def application_list_item_view(
    record: dict[str, Any], state: ApplicationStateView
) -> ApplicationListItemView:
    return ApplicationListItemView.model_validate(
        {
            **record,
            **state.model_dump(mode="python"),
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
                approved_revision_id=row.get("approved_revision_id"),
                artifact_version_id=row.get("artifact_version_id"),
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
        }
    )


def analysis_view(record: dict[str, Any]) -> JobAnalysisView:
    return JobAnalysisView.model_validate(
        {
            **{key: record.get(key) for key in JobAnalysisView.model_fields if key != "analysis"},
            "analysis": record["analysis"],
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


def approved_revision_view(revision: ApprovedRevision, qualification: Any) -> ApprovedRevisionView:
    """Build the public view field by field so stored payload paths cannot leak."""
    return ApprovedRevisionView(
        id=revision.id,
        application_id=revision.application_id,
        version_number=revision.version_number,
        working_draft_id=revision.working_draft_id,
        job_snapshot_id=revision.job_snapshot_id,
        job_analysis_id=revision.job_analysis_id,
        selection_plan_id=revision.selection_plan_id,
        validation_run_id=revision.validation_run_id,
        draft_edit_version=revision.draft_edit_version,
        draft_content_hash=revision.draft_content_hash,
        facts_version=revision.facts_version,
        approved_at=revision.approved_at,
        decision_provenance=revision.decision_provenance,
        ready_qualified=qualification.ready_qualified,
        pdf_artifact_version_id=qualification.pdf_artifact_version_id,
        html_artifact_version_id=qualification.html_artifact_version_id,
        ready_validation=qualification.validation,
    )


def decision_view(record: dict[str, Any]) -> DecisionRecordView:
    return DecisionRecordView.model_validate(
        {
            **{
                key: record.get(key)
                for key in DecisionRecordView.model_fields
                if key != "structured"
            },
            "structured": json.loads(record.get("structured_json") or "{}"),
        }
    )
