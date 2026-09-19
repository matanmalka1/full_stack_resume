"""Analysis/plan activation using a caller-owned transaction, with no external effects."""

from __future__ import annotations

from ...commands import AnalysisResult, AnalyzeCommand, SelectionPlanResult
from ...errors import LineageBroken, StateConflict
from ...ports.analysis_plans import AnalysisPlanStore, AnalysisSelectionSourceReader
from ...ports.transactions import WriteTransaction
from .preparation import PreparedAnalysis
from .selection_plans import AnalysisSelectionService
from .selection_policy import PreparedSelectionPlan


class AnalysisActivation:
    def __init__(self, plans: AnalysisPlanStore, sources: AnalysisSelectionSourceReader):
        self.plans = plans
        self.sources = sources

    def activate(
        self, tx: WriteTransaction, command: AnalyzeCommand, prepared: PreparedAnalysis
    ) -> AnalysisResult:
        # The runner takes this lock as its first statement; direct callers get the
        # same ordering here before reading any source or allocating any version.
        self.plans.lock_application(tx, command.application_id)
        source = self.sources.analysis_source(tx, command.job_snapshot_id)
        if source.application_id != command.application_id:
            raise LineageBroken("job snapshot does not belong to the named Application")
        if source.deleted_at is not None:
            raise StateConflict(f"application is deleted: {command.application_id}")
        analysis_id, selection_plan = self.plans.save_analysis(
            tx,
            command.application_id,
            command.job_snapshot_id,
            prepared.result,
            prepared.plan_manifest,
            provider=prepared.provider,
            model=prepared.model,
            candidate_context_version=prepared.candidate_context_version,
            candidate_context_hash=prepared.candidate_context_hash,
            profile_version=prepared.profile_version,
            selection_policy_version=prepared.selection_policy_version,
            track_emphasis_dependencies=prepared.track_emphasis_dependencies,
            expected_analysis_id=command.expected_analysis_id,
            expected_selection_plan_id=command.expected_selection_plan_id,
            enforce_expected_selection_plan=command.expected_analysis_id is not None,
            refuse_matching_context_operation=command.refuse_matching_context_operation,
        )
        self.plans.set_normalized_role(tx, command.application_id, prepared.normalized_role)
        return AnalysisResult(
            application_id=command.application_id,
            job_snapshot_id=command.job_snapshot_id,
            analysis_id=analysis_id,
            selection_plan_id=selection_plan.id,
            analysis=prepared.result,
        )

    def activate_selection_plan(
        self, tx: WriteTransaction, prepared: PreparedSelectionPlan
    ) -> SelectionPlanResult:
        command = prepared.command
        self.plans.lock_application(tx, command.application_id)
        source = self.sources.selection_source(tx, command.job_analysis_id)
        if source.application_id != command.application_id:
            raise LineageBroken("job analysis does not belong to the named Application")
        if source.deleted_at is not None:
            raise StateConflict(f"application is deleted: {command.application_id}")
        # Re-run the same deterministic policy over rechecked persisted sources
        # and the already-loaded canonical files. No external adapter is called.
        prepared = AnalysisSelectionService.prepare_selection(command, source, prepared.knowledge)
        plan = self.plans.create_selection_plan(
            tx,
            command.application_id,
            command.job_analysis_id,
            prepared.manifest,
            candidate_context_version=prepared.candidate_context_version,
            candidate_context_hash=prepared.candidate_context_hash,
            profile_version=prepared.profile_version,
            selection_policy_version=prepared.selection_policy_version,
            track_emphasis_dependencies=prepared.track_emphasis_dependencies,
            expected_selection_plan_id=command.expected_selection_plan_id,
            enforce_expected_selection_plan=command.enforce_expected_selection_plan,
            refuse_matching_context_operation=command.refuse_matching_context_operation,
        )
        return SelectionPlanResult(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            selection_plan_id=plan.id,
            plan=plan,
        )
