from __future__ import annotations

from ..commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
    ProposeSelectionPlanCommand,
    SelectionPlanResult,
)
from ..errors import LineageBroken, UnknownRecord
from ..ports import PreparationRepository
from .analysis_correction import AnalysisCorrection
from .analysis_preparation import AnalysisPreparation, PreparedAnalysis
from .analysis_selection import AnalysisSelection, PreparedSelectionProposal
from .analysis_selection_service import AnalysisSelectionService
from .base import ServiceBase

ACCEPTANCE_ACTOR = "user"


class AnalysisService(ServiceBase[PreparationRepository]):
    """Coordinate AI analysis, user decisions, and selection-plan activation."""

    def _analysis_record(
        self,
        application_id: str,
        job_analysis_id: str,
        repository: PreparationRepository | None = None,
    ) -> dict:
        """One named analysis, proven to belong to the named Application.

        Both IDs are explicit. Resolving the analysis from the Application would
        be `latest` inside a command, which is exactly what lets a decision land
        on something other than what the user was looking at.
        """
        try:
            record = (repository or self.repo).get_analysis(job_analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job analysis: {job_analysis_id}") from exc
        if record["application_id"] != application_id:
            raise LineageBroken(
                f"job analysis {job_analysis_id} does not belong to application {application_id}"
            )
        return record

    def prepare(
        self, command: AnalyzeCommand, *, operation_id: str | None = None
    ) -> PreparedAnalysis:
        return AnalysisPreparation.prepare(self, command, operation_id=operation_id)

    def activate(
        self,
        command: AnalyzeCommand,
        prepared: PreparedAnalysis,
        repository: PreparationRepository | None = None,
    ) -> AnalysisResult:
        """Commit a prepared result after the runner's final optimistic check."""
        repo = repository or self.repo
        analysis_id, selection_plan = repo.save_analysis(
            command.application_id,
            command.job_snapshot_id,
            prepared.result,
            prepared.plan_manifest,
            provider=prepared.provider,
            model=prepared.model,
            candidate_context_version=prepared.candidate_context_version,
            candidate_context_hash=prepared.candidate_context_hash,
            profile_version=prepared.profile_version,
            # The manifest's own `policy_version` is the label the policy files
            # declare; editing a policy does not move it. The store's `version`
            # hashes the policy content, so it is the value a later change can
            # actually be compared against.
            selection_policy_version=prepared.selection_policy_version,
            track_emphasis_dependencies=prepared.track_emphasis_dependencies,
            # Validated against the analysis about to be written, not the one
            # the user decided on: an interpretation correction can remove a gap,
            # and an id that no longer names one is refused rather than stored.
            accepted_requirement_ids=sorted(
                set(
                    AnalysisSelection.acceptable_requirement_ids(
                        list(command.accepted_requirement_ids),
                        prepared.result,
                        command.expected_selection_plan_id,
                    )
                )
            ),
            acceptance_actor=ACCEPTANCE_ACTOR,
            acceptance_reason=command.acceptance_reason,
            expected_analysis_id=command.expected_analysis_id,
            expected_selection_plan_id=command.expected_selection_plan_id,
            enforce_expected_selection_plan=command.expected_analysis_id is not None,
            refuse_matching_context_operation=command.refuse_matching_context_operation,
        )
        repo.set_normalized_role(command.application_id, prepared.normalized_role)
        return AnalysisResult(
            application_id=command.application_id,
            job_snapshot_id=command.job_snapshot_id,
            analysis_id=analysis_id,
            selection_plan_id=selection_plan.id,
            analysis=prepared.result,
        )

    def create_selection_plan(
        self,
        command: CreateSelectionPlanCommand,
        repository: PreparationRepository | None = None,
    ) -> SelectionPlanResult:
        return AnalysisSelectionService.create_selection_plan(self, command, repository)

    def prepare_selection_proposal(
        self, command: ProposeSelectionPlanCommand, *, operation_id: str
    ) -> PreparedSelectionProposal:
        return AnalysisSelectionService.prepare_selection_proposal(
            self, command, operation_id=operation_id
        )

    def activate_selection_proposal(
        self,
        prepared: PreparedSelectionProposal,
        repository: PreparationRepository | None = None,
    ) -> SelectionPlanResult:
        return AnalysisSelectionService.activate_selection_proposal(self, prepared, repository)

    def apply_analysis_decisions(
        self, command: ApplyAnalysisDecisionsCommand
    ) -> AnalysisDecisionsResult:
        return AnalysisCorrection.apply_analysis_decisions(self, command)
