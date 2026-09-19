"""Create and propose selection plans from an existing AI analysis."""

from __future__ import annotations

from dataclasses import asdict

from ....domain.analysis.projection import gaps as project_gaps
from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.taxonomy import Emphasis
from ....domain.knowledge import Knowledge
from ....domain.profiles import allowed_fact_pool
from ...commands import CreateSelectionPlanCommand, ProposeSelectionPlanCommand
from ...errors import PreconditionFailed, ProposalRejected
from ...ports import SelectionPlanContext
from ...ports.analysis_plans import SelectionSource
from ..proposals import evidence_attached, fact_context, refuse_facts_outside_the_pool
from .selection_policy import AnalysisSelection, PreparedSelectionPlan, PreparedSelectionProposal


class AnalysisSelectionService:
    @staticmethod
    def _non_excludable_selected_facts(
        analysis: JobAnalysis,
        knowledge: Knowledge,
        selected_fact_ids: list[str],
    ) -> list[str]:
        """Derive facts whose individual exclusion violates selection policy.

        This is advisory context for the provider, never an authorization rule:
        the complete proposed overlay still runs through ``build_selection``.
        """
        protected: list[str] = []
        for fact_id in selected_fact_ids:
            try:
                AnalysisSelection.manifest(
                    analysis,
                    knowledge,
                    excluded_fact_ids=frozenset({fact_id}),
                )
            except PreconditionFailed:
                protected.append(fact_id)
        return sorted(protected)

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
    def prepare_selection_plan(
        service,
        command: CreateSelectionPlanCommand,
    ) -> PreparedSelectionPlan:
        """Read sources and build a deterministic overlay before opening a write scope."""
        source = service.selection_source(command.application_id, command.job_analysis_id)
        service.refuse_deleted(source.application_id, source.deleted_at)
        return AnalysisSelectionService.prepare_selection(command, source, service.load_knowledge())

    @staticmethod
    def prepare_selection(
        command: CreateSelectionPlanCommand,
        source: SelectionSource,
        knowledge: Knowledge,
    ) -> PreparedSelectionPlan:
        """Pure policy validation, shared by preparation and atomic activation."""
        analysis: JobAnalysis = source.analysis
        active_plan = source.active_plan
        try:
            effective_emphasis = (
                Emphasis(command.emphasis_override)
                if command.emphasis_override is not None
                else active_plan.emphasis
                if active_plan is not None
                else analysis.emphasis
            )
        except ValueError as exc:
            raise PreconditionFailed(f"unknown Emphasis: {command.emphasis_override}") from exc
        explicit_emphasis = (
            effective_emphasis
            if command.emphasis_override is not None
            else active_plan.emphasis_override
            if active_plan is not None
            else None
        )
        selection_analysis = analysis.model_copy(update={"emphasis": effective_emphasis})
        AnalysisSelectionService.refuse_moved_sources(command, knowledge)
        AnalysisSelection.profile(selection_analysis, knowledge.profiles)
        manifest = AnalysisSelection.manifest(
            selection_analysis,
            knowledge,
            pinned_fact_ids=frozenset(command.pinned_fact_ids),
            excluded_fact_ids=frozenset(command.excluded_fact_ids),
        )
        manifest = manifest.model_copy(update={"emphasis_override": explicit_emphasis})
        return PreparedSelectionPlan(
            command=command,
            knowledge=knowledge,
            manifest=manifest,
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=knowledge.profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": analysis.track.value,
                "emphasis": effective_emphasis.value,
            },
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
        source = service.selection_source(command.application_id, command.job_analysis_id)
        service.refuse_deleted(source.application_id, source.deleted_at)
        analysis: JobAnalysis = source.analysis
        active_plan = source.active_plan
        effective_analysis = (
            analysis.model_copy(update={"emphasis": active_plan.emphasis})
            if active_plan is not None
            else analysis
        )
        knowledge = service.load_knowledge()
        profile = AnalysisSelection.profile(effective_analysis, knowledge.profiles)
        allowed = allowed_fact_pool(profile)
        manifest = AnalysisSelection.manifest(effective_analysis, knowledge)
        non_excludable = AnalysisSelectionService._non_excludable_selected_facts(
            effective_analysis,
            knowledge,
            manifest.selected_fact_ids,
        )

        service.assert_provider_io_allowed()
        answered = service.provider.propose_selection_plan(
            SelectionPlanContext(
                job_analysis={
                    "track": analysis.track.value,
                    "profile": analysis.profile.value,
                    "emphasis": effective_analysis.emphasis.value,
                    "language": analysis.language,
                    "keywords": list(analysis.keywords),
                    "gaps": [
                        asdict(gap) for gap in project_gaps(analysis.requirements, knowledge.facts)
                    ],
                },
                allowed_facts=fact_context(
                    knowledge.facts, sorted(allowed), effective_analysis.language
                ),
                deterministic_selection={
                    "selected_fact_ids": list(manifest.selected_fact_ids),
                    "non_excludable_fact_ids": non_excludable,
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
        selection_command = CreateSelectionPlanCommand(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            pinned_fact_ids=list(proposal.pinned_fact_ids),
            excluded_fact_ids=list(proposal.excluded_fact_ids),
            emphasis_override=(
                active_plan.emphasis_override.value
                if active_plan is not None and active_plan.emphasis_override is not None
                else None
            ),
            expected_candidate_context_hash=command.expected_candidate_context_hash,
            expected_facts_version=command.expected_facts_version,
            expected_profile_version=command.expected_profile_version,
            expected_selection_policy_version=command.expected_selection_policy_version,
            expected_selection_plan_id=command.expected_selection_plan_id,
            enforce_expected_selection_plan=command.enforce_expected_selection_plan,
        )
        with evidence_attached(evidence):
            try:
                selection = AnalysisSelectionService.prepare_selection_plan(
                    service, selection_command
                )
            except PreconditionFailed as exc:
                raise ProposalRejected(
                    "propose_selection_plan produced an overlay rejected by selection policy",
                    unsupported=sorted(
                        set(proposal.pinned_fact_ids) | set(proposal.excluded_fact_ids)
                    ),
                ) from exc
        return PreparedSelectionProposal(
            command=selection_command,
            proposal=proposal,
            evidence=evidence,
            selection=selection,
        )
