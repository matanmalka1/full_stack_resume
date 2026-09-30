"""Propose a CV document selection from its analysis (the AI form of update_selection)."""

from __future__ import annotations

from dataclasses import asdict

from ....domain.analysis.projection import gaps as project_gaps
from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.knowledge import Profile
from ....domain.facts import FactStore
from ....domain.knowledge import Knowledge
from ....domain.profiles import allowed_fact_pool
from ....domain.selection import STRUCTURAL_STYLES
from ...commands import ProposeSelectionCommand
from ...errors import PreconditionFailed, ProposalRejected
from ...ports import SelectionPlanContext, SelectionSectionContext
from ..documents import build_document_selection, refuse_authored_wording, refuse_deleted
from ..proposals import evidence_attached, fact_context, refuse_facts_outside_the_pool
from .selection_policy import AnalysisSelection, PreparedSelectionProposal


class AnalysisSelectionService:
    @staticmethod
    def _section_constraints(
        profile: Profile, facts: FactStore, capacity: dict[str, int]
    ) -> list[SelectionSectionContext]:
        """Describe the same per-section pin capacity that selection enforces.

        Structural facts, Profile pins and role-block floor reservations consume
        the section budget before an AI overlay is considered. `capacity` comes
        from the domain's own selection code, so the number offered here is the
        number `build_selection` will honour. The full selection policy still
        validates the proposal, including required-tag coverage.
        """
        sections: list[SelectionSectionContext] = []
        for spec in profile.sections:
            fixed = [
                fact_id
                for fact_id in spec.fact_ids
                if fact_id in spec.pinned_fact_ids
                or facts.get(fact_id, canonical_only=True).resume_style in STRUCTURAL_STYLES
            ]
            budget = spec.max_claims if spec.max_claims is not None else len(spec.fact_ids)
            sections.append(
                SelectionSectionContext(
                    section=spec.name_en,
                    fact_ids=list(spec.fact_ids),
                    max_claims=budget,
                    fixed_fact_ids=fixed,
                    max_additional_pins=capacity[spec.name_en],
                )
            )
        return sections

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
    def prepare_selection_proposal(
        service,
        command: ProposeSelectionCommand,
        *,
        operation_id: str,
    ) -> PreparedSelectionProposal:
        """§14 `propose_selection`: ask for an overlay, and refuse anything outside the pool.

        No provider call happens inside a synchronous HTTP request, so this is only
        ever reached from the Operation runner's execute phase. Nothing durable is
        written here beyond the preserved response: the overlay is validated by the
        same selection policy `update_selection` uses, and written only at activation
        after the `expected_document_hash` check. Content the engine composed is
        rebuilt from the activated selection; authored wording is refused here, before
        the provider is called.
        """
        source = service.document_source(command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        document = source.document
        refuse_authored_wording(document.content)
        analysis: JobAnalysis = source.analysis
        effective_analysis = analysis.model_copy(update={"emphasis": document.selection.emphasis})
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
                sections=AnalysisSelectionService._section_constraints(
                    profile,
                    knowledge.facts,
                    AnalysisSelection.pin_capacity(effective_analysis, knowledge),
                ),
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
            try:
                selection = build_document_selection(
                    analysis,
                    knowledge,
                    current=document.selection,
                    pinned_fact_ids=proposal.pinned_fact_ids,
                    excluded_fact_ids=proposal.excluded_fact_ids,
                    ai_rationale=proposal.rationale,
                )
            except PreconditionFailed as exc:
                raise ProposalRejected(
                    "propose_selection_plan produced an overlay rejected by selection policy",
                    unsupported=sorted(
                        set(proposal.pinned_fact_ids) | set(proposal.excluded_fact_ids)
                    ),
                ) from exc
        return PreparedSelectionProposal(
            command=command,
            proposal=proposal,
            evidence=evidence,
            selection=selection,
        )
