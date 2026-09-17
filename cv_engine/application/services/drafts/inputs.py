"""Pure checks and lineage shared by draft consumers."""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.drafts import DraftDocument, WorkingDraft
from ....domain.contracts.records import ValidationRunLineage
from ....domain.contracts.selection import SelectionPlan
from ....domain.drafts import build_draft
from ....domain.knowledge import Knowledge
from ....domain.selection import MissingFactRendering as DomainMissingFactRendering
from ...errors import MissingFactRendering, PreconditionFailed, StateConflict


def require_working_version(working: WorkingDraft, expected_version: int) -> None:
    if not working.active:
        raise PreconditionFailed(f"working draft {working.id} is no longer the active draft")
    if working.edit_version != expected_version:
        raise StateConflict(
            f"working draft {working.id} is at edit version {working.edit_version}, not {expected_version}"
        )


def validation_lineage(working: WorkingDraft, knowledge: Knowledge) -> ValidationRunLineage:
    return ValidationRunLineage(
        working_draft_id=working.id,
        edit_version=working.edit_version,
        content_hash=working.content_hash,
        job_snapshot_id=working.source.job_snapshot_id,
        job_analysis_id=working.job_analysis_id,
        selection_plan_id=working.selection_plan_id,
        knowledge_context_hash=knowledge.document_context_hash(),
        validator_versions={"draft": "2.0"},
    )


def compose(
    *,
    application_id: str,
    job_snapshot_id: str,
    job_analysis_id: str,
    analysis: JobAnalysis,
    plan: SelectionPlan,
    knowledge: Knowledge,
) -> DraftDocument:
    """The deterministic document one analysis and one plan produce.

    Shared by generation and by `apply_selection_change`, which has to
    rebuild the same document against a different plan. A second call to
    `build_draft` with its own argument list is how the two would drift.
    """
    try:
        return build_draft(
            application_id=application_id,
            job_snapshot_id=job_snapshot_id,
            job_analysis_id=job_analysis_id,
            analysis=analysis,
            profile=knowledge.profiles.get(analysis.profile),
            facts=knowledge.facts,
            policies=knowledge.policies,
            candidate=knowledge.candidate,
            presentations=knowledge.presentations,
            selection=plan.plan,
        )
    except DomainMissingFactRendering as exc:
        raise MissingFactRendering(exc.fact_id, exc.language) from exc
    except ValueError as exc:
        raise PreconditionFailed(f"draft could not be built: {exc}") from exc


def require_content_hash(working: WorkingDraft, expected_content_hash: str) -> None:
    if working.content_hash != expected_content_hash:
        raise StateConflict(
            f"working draft {working.id} has content hash {working.content_hash}, not {expected_content_hash}"
        )
