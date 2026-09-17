"""§14: changing selection, committing the plan and rebuilt draft together."""

from __future__ import annotations

from ....domain.drafts import manually_edited
from ...commands import (
    ApplySelectionChangeCommand,
    CreateSelectionPlanCommand,
    SelectionChangeResult,
)
from ...errors import InfrastructureFailure, PreconditionFailed, StateConflict
from ...ports import (
    ArtifactStore,
    KnowledgeStore,
    TransactionManager,
)
from ...ports.selection_drafts import SelectionDraftStore
from ..analysis.service import AnalysisService, load_analysis_knowledge
from .inputs import compose


class SelectionChangeService:
    """Own the atomic selection-plan and working-draft change transaction."""

    def __init__(
        self,
        transactions: TransactionManager,
        drafts: SelectionDraftStore,
        knowledge: KnowledgeStore,
        artifacts: ArtifactStore,
    ):
        self.transactions = transactions
        self.drafts = drafts
        self.knowledge = knowledge
        self.artifacts = artifacts

    def apply(
        self, command: ApplySelectionChangeCommand, *, analysis_service: AnalysisService
    ) -> SelectionChangeResult:
        with self.transactions.read() as tx:
            working = self.drafts.working_draft(tx, command.working_draft_id)
        if not working.active:
            raise PreconditionFailed(f"working draft {working.id} is no longer the active draft")
        if working.edit_version != command.expected_edit_version:
            raise StateConflict(
                f"working draft {working.id} is at edit version {working.edit_version}, not {command.expected_edit_version}"
            )
        source = analysis_service.selection_source(working.application_id, working.job_analysis_id)
        analysis_service.refuse_deleted(source.application_id, source.deleted_at)
        if manually_edited(working.source):
            raise PreconditionFailed(
                "this draft carries manual wording that a deterministic rebuild would discard; use regenerate_section or regenerate_claim to change its selection"
            )
        knowledge = load_analysis_knowledge(self.knowledge)
        prepared = analysis_service.prepare_selection_plan(
            CreateSelectionPlanCommand(
                application_id=working.application_id,
                job_analysis_id=working.job_analysis_id,
                pinned_fact_ids=list(command.pinned_fact_ids),
                excluded_fact_ids=list(command.excluded_fact_ids),
            )
        )
        with self.transactions.write() as tx:
            created = analysis_service.activation.activate_selection_plan(tx, prepared)
            document = compose(
                application_id=working.application_id,
                job_snapshot_id=source.job_snapshot_id,
                job_analysis_id=working.job_analysis_id,
                analysis=source.analysis,
                plan=created.plan,
                knowledge=knowledge,
            )
            changed = self.drafts.update_selection(
                tx, working.id, working.edit_version, document, created.selection_plan_id
            )
        try:
            self.artifacts.write_working_draft(changed.source)
        except OSError as exc:
            raise InfrastructureFailure(f"could not store working draft: {exc}") from exc
        return SelectionChangeResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            plan=created.plan,
        )
