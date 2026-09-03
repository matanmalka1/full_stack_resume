"""State every draft use case shares: one draft version, one composed document."""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.drafts import (
    DraftDocument,
    WorkingDraft,
)
from ....domain.contracts.records import ValidationRunLineage
from ....domain.contracts.selection import SelectionPlan
from ....domain.drafts import build_draft
from ....domain.knowledge import Knowledge
from ....domain.selection import MissingFactRendering as DomainMissingFactRendering
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    MissingFactRendering,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ...ports import DraftRepository
from ..base import ServiceBase


class DraftServiceBase(ServiceBase[DraftRepository]):
    """The reads and writes the working-draft use cases have in common.

    Split out of `DraftService` so each use-case group owns its own module and
    still resolves one draft version, composes one document, and commits one
    edit through the same code. The class is not wired anywhere on its own: it
    is the base every group in this package extends, and `DraftService`
    assembles them.
    """

    @staticmethod
    def _lineage(working: WorkingDraft, knowledge: Knowledge) -> ValidationRunLineage:
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

    @staticmethod
    def _compose(
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

    def _working(self, working_draft_id: str, expected_version: int) -> WorkingDraft:
        """One exact draft version, named by ID, or the refusal that says why.

        The version is checked here rather than only in the UPDATE clause so a
        read-only command - validate, above all - refuses a stale client with
        the same `409` a save would, instead of quietly reporting on content the
        client is no longer looking at.
        """
        try:
            working = self.repo.working_draft(working_draft_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc
        if not working.active:
            raise PreconditionFailed(
                f"working draft {working_draft_id} is no longer the active draft"
            )
        if working.edit_version != expected_version:
            raise StateConflict(
                f"working draft {working_draft_id} is at edit version "
                f"{working.edit_version}, not {expected_version}"
            )
        return working

    def _commit_edit(self, working: WorkingDraft, source: DraftDocument) -> WorkingDraft:
        changed = self.repo.update_working_draft(
            working.id,
            working.edit_version,
            source,
        )
        return changed
