"""§14: changing what the draft selects, plan and rebuilt document in one write."""

from __future__ import annotations

from typing import cast

from ....domain.drafts import manually_edited
from ....domain.models import JobAnalysis
from ...commands import (
    ApplySelectionChangeCommand,
    CreateSelectionPlanCommand,
    SelectionChangeResult,
)
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    PreconditionFailed,
)
from ...ports import PreparationRepository
from ..analysis import AnalysisService
from .common import DraftServiceBase


class DraftSelectionChange(DraftServiceBase):
    """A deterministic re-selection over the draft that is already active."""

    def apply_selection_change(
        self,
        command: ApplySelectionChangeCommand,
        *,
        analysis_service: AnalysisService,
    ) -> SelectionChangeResult:
        """§14: a deterministic selection change, plan and draft committed together.

        The new SelectionPlan and the draft that is built from it are one write.
        A plan that landed without its draft would be a decision the document
        does not reflect; a draft that landed without its plan would be content
        with no record of what chose it.

        A draft carrying manual wording takes the other branch §14 names. The
        rebuild is deterministic, so it would replace the user's own sentences
        with the engine's without asking - which is the definition of a change
        that needs wording judgment.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        if manually_edited(working.source):
            raise PreconditionFailed(
                "this draft carries manual wording that a deterministic rebuild would "
                "discard; use regenerate_section or regenerate_claim to change its "
                "selection"
            )
        knowledge = self.load_knowledge()
        record = self.repo.get_analysis(working.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]
        with self.repo.unit_of_work() as uow:
            transaction = self.repo.bind(uow)
            created = analysis_service.create_selection_plan(
                CreateSelectionPlanCommand(
                    application_id=working.application_id,
                    job_analysis_id=working.job_analysis_id,
                    pinned_fact_ids=list(command.pinned_fact_ids),
                    excluded_fact_ids=list(command.excluded_fact_ids),
                ),
                cast(PreparationRepository, transaction),
            )
            source = self._compose(
                application_id=working.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                job_analysis_id=working.job_analysis_id,
                analysis=analysis,
                plan=created.plan,
                knowledge=knowledge,
            )
            changed = transaction.update_working_draft(
                working.id,
                working.edit_version,
                source,
                selection_plan_id=created.selection_plan_id,
            )
            uow.commit()
        self.store_working_draft(changed.source)
        return SelectionChangeResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            plan=created.plan,
        )
