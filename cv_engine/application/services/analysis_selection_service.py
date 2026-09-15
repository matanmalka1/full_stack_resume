"""Create and propose selection plans from an existing AI analysis."""

from __future__ import annotations

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.taxonomy import Emphasis
from ...domain.contracts.selection import SelectionPlan
from ...domain.profiles import allowed_fact_pool
from ..commands import CreateSelectionPlanCommand, ProposeSelectionPlanCommand, SelectionPlanResult
from ..errors import PreconditionFailed, UnknownRecord
from ..ports import PreparationRepository, SelectionPlanContext
from .analysis_selection import AnalysisSelection, PreparedSelectionProposal
from .proposals import evidence_attached, fact_context, refuse_facts_outside_the_pool


class AnalysisSelectionService:
    @staticmethod
    def _active_plan(
        repo: PreparationRepository, application_id: str, job_analysis_id: str
    ) -> SelectionPlan | None:
        """The latest plan only participates when it belongs to this analysis."""
        try:
            latest = repo.latest_selection_plan(application_id)
        except UnknownRecord:
            return None
        return latest if latest.job_analysis_id == job_analysis_id else None

    @staticmethod
    def refuse_moved_sources(command: CreateSelectionPlanCommand, knowledge) -> None:
        """The optimistic check on what the user was looking at when they decided.

        Each expectation is optional and checked only when the client states it.
        A client that states nothing is planning against current Knowledge and
        says so; a client that states a version which has since moved is
        refused, because the candidate accounting it showed the user no longer
        describes what this plan would contain.
        """
        expected = (
            (
                "candidate context",
                command.expected_candidate_context_hash,
                knowledge.candidate.version_hash,
            ),
            ("Facts store", command.expected_facts_version, knowledge.facts.version),
            ("Profile store", command.expected_profile_version, knowledge.profiles.version),
            (
                "selection policy",
                command.expected_selection_policy_version,
                knowledge.policies.version,
            ),
        )
        moved = [name for name, want, have in expected if want is not None and want != have]
        if moved:
            raise PreconditionFailed(
                f"Knowledge moved since the decision was made: {', '.join(moved)}"
            )

    @staticmethod
    def create_selection_plan(
        service,
        command: CreateSelectionPlanCommand,
        repository: PreparationRepository | None = None,
    ) -> SelectionPlanResult:
        """§13, deterministic form: synchronous, and it returns the plan itself.

        No provider call happens inside a synchronous request, so this path
        never needs one. The AI `propose_selection_plan` mode is the same
        command's asynchronous form and arrives with the rest of the AI tasks.

        `repository` is the same escape `activate` takes: a caller that has to
        commit this plan together with something else binds its own UnitOfWork
        and passes the bound repository, so `apply_selection_change` gets one
        implementation of the overlay rather than a second copy of it.
        """
        service.load_active_application(command.application_id)
        repo = repository or service.repo
        record = service._analysis_record(command.application_id, command.job_analysis_id, repo)
        analysis: JobAnalysis = record["analysis"]
        active_plan = AnalysisSelectionService._active_plan(
            repo, command.application_id, command.job_analysis_id
        )
        try:
            effective_emphasis = (
                Emphasis(command.emphasis_override)
                if command.emphasis_override is not None
                else active_plan.plan.emphasis
                if active_plan is not None
                else analysis.emphasis
            )
        except ValueError as exc:
            raise PreconditionFailed(f"unknown Emphasis: {command.emphasis_override}") from exc
        explicit_emphasis = (
            effective_emphasis
            if command.emphasis_override is not None
            else active_plan.plan.emphasis_override
            if active_plan is not None
            else None
        )
        selection_analysis = analysis.model_copy(update={"emphasis": effective_emphasis})
        knowledge = service.load_knowledge()
        AnalysisSelectionService.refuse_moved_sources(command, knowledge)
        AnalysisSelection.profile(selection_analysis, knowledge.profiles)
        manifest = AnalysisSelection.manifest(
            selection_analysis,
            knowledge,
            pinned_fact_ids=frozenset(command.pinned_fact_ids),
            excluded_fact_ids=frozenset(command.excluded_fact_ids),
        )
        manifest = manifest.model_copy(update={"emphasis_override": explicit_emphasis})
        plan = repo.create_selection_plan(
            command.application_id,
            command.job_analysis_id,
            manifest,
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=knowledge.profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": analysis.track.value,
                "emphasis": effective_emphasis.value,
            },
            new_acceptances=AnalysisSelection.new_acceptances(command, analysis),
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

    @staticmethod
    def prepare_selection_proposal(
        service,
        command: ProposeSelectionPlanCommand,
        *,
        operation_id: str,
    ) -> PreparedSelectionProposal:
        """§13, AI form: ask for an overlay, and refuse anything outside the pool.

        No provider call happens inside a synchronous HTTP request, so this is
        only ever reached from the Operation runner's execute phase. Nothing
        durable is written here beyond the preserved response: the Proposal is
        turned into a deterministic command and committed by `activate`, after
        the runner's final source check.
        """
        record = service._analysis_record(command.application_id, command.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]
        active_plan = AnalysisSelectionService._active_plan(
            service.repo, command.application_id, command.job_analysis_id
        )
        effective_analysis = (
            analysis.model_copy(update={"emphasis": active_plan.plan.emphasis})
            if active_plan is not None
            else analysis
        )
        knowledge = service.load_knowledge()
        profile = AnalysisSelection.profile(effective_analysis, knowledge.profiles)
        allowed = allowed_fact_pool(profile)
        manifest = AnalysisSelection.manifest(effective_analysis, knowledge)

        answered = service.provider.propose_selection_plan(
            SelectionPlanContext(
                job_analysis={
                    "track": analysis.track.value,
                    "profile": analysis.profile.value,
                    "emphasis": effective_analysis.emphasis.value,
                    "language": analysis.language,
                    "keywords": list(analysis.keywords),
                    "gaps": [gap.model_dump(mode="json") for gap in analysis.gaps],
                },
                allowed_facts=fact_context(
                    knowledge.facts, sorted(allowed), effective_analysis.language
                ),
                deterministic_selection={
                    "selected_fact_ids": list(manifest.selected_fact_ids),
                    "emphasis_policy_version": manifest.emphasis_policy_version,
                },
            ),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        evidence = service.preserve(
            command.application_id,
            operation_id,
            "propose_selection_plan",
            answered.provenance,
        )
        proposal = answered.proposal
        with evidence_attached(evidence):
            refuse_facts_outside_the_pool(
                set(proposal.pinned_fact_ids) | set(proposal.excluded_fact_ids),
                allowed,
                task="propose_selection_plan",
            )
        return PreparedSelectionProposal(
            command=CreateSelectionPlanCommand(
                application_id=command.application_id,
                job_analysis_id=command.job_analysis_id,
                pinned_fact_ids=list(proposal.pinned_fact_ids),
                excluded_fact_ids=list(proposal.excluded_fact_ids),
                emphasis_override=(
                    active_plan.plan.emphasis_override.value
                    if active_plan is not None and active_plan.plan.emphasis_override is not None
                    else None
                ),
                expected_candidate_context_hash=command.expected_candidate_context_hash,
                expected_facts_version=command.expected_facts_version,
                expected_profile_version=command.expected_profile_version,
                expected_selection_policy_version=command.expected_selection_policy_version,
                expected_selection_plan_id=command.expected_selection_plan_id,
                enforce_expected_selection_plan=command.enforce_expected_selection_plan,
            ),
            proposal=proposal,
            evidence=evidence,
        )

    @staticmethod
    def activate_selection_proposal(
        service,
        prepared: PreparedSelectionProposal,
        repository: PreparationRepository | None = None,
    ) -> SelectionPlanResult:
        """Commit the proposed overlay through the deterministic command.

        Every check `create_selection_plan` makes runs again here, against
        Knowledge as it is at activation - not as it was when the provider was
        asked. That is the optimistic rule §13 requires, and it is why the AI
        path cannot commit a plan the deterministic path would have refused.
        """
        repo = repository or service.repo
        return service.create_selection_plan(prepared.command, repo)
