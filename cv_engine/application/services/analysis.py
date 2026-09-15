from __future__ import annotations

from ...domain.analysis.approval import (
    ACCEPTED_INCOMPLETE_ANALYSIS,
)
from ...domain.analysis.assembly import build_analysis, rebase_requirements
from ...domain.analysis.requirements.ai_extraction import (
    RequirementExtractionRejected,
    apply_interpretation_corrections,
    extraction_is_failed,
    verify_and_cover_extraction,
)
from ...domain.analysis.requirements.segmentation import requirement_lines
from ...domain.contracts.analysis import (
    JobAnalysis,
    OverrideKey,
)
from ...domain.contracts.selection import (
    SelectionPlan,
)
from ...domain.contracts.taxonomy import Emphasis
from ...domain.profiles import allowed_fact_pool
from ...util import utc_now
from ..commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
    ProposeSelectionPlanCommand,
    SelectionPlanResult,
)
from ..errors import (
    ApplicationError,
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    ProviderInvalidOutput,
    StateConflict,
    UnknownRecord,
)
from ..ports import (
    JobAnalysisContext,
    PreparationRepository,
    RequirementExtractionContext,
    SelectionPlanContext,
)
from .analysis_correction import revise_classification
from .analysis_preparation import PreparedAnalysis
from .analysis_selection import AnalysisSelection, PreparedSelectionProposal
from .base import ServiceBase
from .proposals import (
    ProviderEvidence,
    analysis_fact_context,
    evidence_attached,
    fact_context,
    refuse_facts_outside_the_pool,
)

#: Single-user product: there is one actor, and the record says so plainly
#: rather than inventing an identity the system does not have.
ACCEPTANCE_ACTOR = "user"


class AnalysisService(ServiceBase[PreparationRepository]):
    """Classification, fit, and the analysis record."""

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
        """Validate and compute an analysis without mutating durable application state.

        `operation_id` is required in AI mode and unused otherwise. It is
        where the sanitized provider response is preserved, and it is the
        Operation's own ID rather than the analysis's, so a retry - which is
        a second Operation - writes beside the first attempt's evidence
        instead of colliding with it.
        """
        try:
            snapshot = self.repo.get_snapshot(command.job_snapshot_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job snapshot: {command.job_snapshot_id}") from exc
        if snapshot["application_id"] != command.application_id:
            raise LineageBroken(
                f"job snapshot {command.job_snapshot_id} does not belong to application "
                f"{command.application_id}"
            )
        try:
            job_text = self.snapshot_payloads.read_snapshot(
                snapshot["payload_path"],
                snapshot["source_hash"],
            )
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        knowledge = self.load_knowledge()
        profiles = knowledge.profiles
        if command.provider != "openai" or operation_id is None:
            raise PreconditionFailed("analysis requires an OpenAI Operation")
        evidence: ProviderEvidence | None = None
        extraction_evidence: ProviderEvidence | None = None
        try:
            extracted_answer = self.provider.propose_requirement_extraction(
                RequirementExtractionContext(
                    job_text=job_text,
                    requirement_lines=[
                        {
                            "start": line.start,
                            "end": line.end,
                            "text": line.text,
                            "section": line.section,
                        }
                        for line in requirement_lines(job_text, knowledge.requirement_concepts)
                    ],
                    candidate_facts=analysis_fact_context(knowledge.facts),
                ),
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            extraction_evidence = self.preserve(
                command.application_id,
                operation_id,
                "propose_requirement_extraction",
                extracted_answer.provenance,
            )
            try:
                (
                    verified_requirements,
                    unmapped,
                    understanding,
                    unmatched_lines,
                ) = verify_and_cover_extraction(
                    extracted_answer.proposal,
                    source_text=job_text,
                    normalized_hash=snapshot["normalized_hash"],
                    facts=knowledge.facts,
                    concepts=knowledge.requirement_concepts,
                    task_version=extracted_answer.provenance.context.task_contract_version,
                    prompt_version=extracted_answer.provenance.context.prompt_version,
                )
            except RequirementExtractionRejected as exc:
                # The sanitized response was already preserved and registered
                # above via `self.preserve` (invariant 15: a refused output
                # stays inactive immutable evidence rather than being dropped
                # at the raise site). `.evidence` is set, not just
                # `provenance=`, so `_preserve_rejected` finds it already
                # registered and only adds the missing Operation output
                # reference - calling `self.preserve` a second time on the
                # same payload would collide on `artifact_versions.path`
                # UNIQUE, exactly as that function's docstring warns against.
                failure = ProviderInvalidOutput(str(exc), provenance=extracted_answer.provenance)
                failure.evidence = extraction_evidence
                raise failure from exc
            extraction_namespace = (
                f"ai:{extracted_answer.provenance.context.task_contract_version}:"
                f"{extracted_answer.provenance.context.prompt_version}"
            )
            answered = self.provider.propose_job_analysis(
                JobAnalysisContext(
                    job_text=job_text,
                    requirements=[item.model_dump(mode="json") for item in verified_requirements],
                    overrides={
                        key: value
                        for key, value in {
                            "track": command.track_override,
                            "profile": command.profile_override,
                            "emphasis": command.emphasis_override,
                            "language": command.language_override,
                        }.items()
                        if value is not None
                    },
                ),
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            evidence = self.preserve(
                command.application_id, operation_id, "propose_job_analysis", answered.provenance
            )
            overrides = {
                key: value
                for key, value in {
                    "track": command.track_override,
                    "profile": command.profile_override,
                    "emphasis": command.emphasis_override,
                    "language": command.language_override,
                }.items()
                if value is not None
            }
            try:
                result = build_analysis(
                    requirements=verified_requirements,
                    extraction_version=extraction_namespace,
                    extraction_failed=extraction_is_failed(
                        job_text, verified_requirements, knowledge.requirement_concepts
                    ),
                    requirements_absent=not verified_requirements,
                    requirements_unmapped=bool(unmatched_lines) and bool(verified_requirements),
                    proposal=answered.proposal,
                    profiles=profiles,
                    facts=knowledge.facts,
                    unmapped_statements=unmapped,
                    understanding=understanding,
                    overrides=overrides,
                )
            except ValueError as exc:
                failure = ProviderInvalidOutput(str(exc), provenance=answered.provenance)
                failure.evidence = evidence
                raise failure from exc
            used_provider = answered.provenance.context.provider
            used_model = answered.provenance.context.model
        except ApplicationError as exc:
            exc.completed_evidence = tuple(
                item for item in (extraction_evidence, evidence) if item is not None
            )
            raise

        accepted: dict[str, str] = {
            **({"fit": "accepted-low-fit"} if command.accept_low_fit else {}),
            **(
                {"analysis": ACCEPTED_INCOMPLETE_ANALYSIS}
                if command.accept_incomplete_analysis
                else {}
            ),
        }
        if accepted:
            # Rebuilt through validation rather than model_copy(update=...), which
            # would skip the model validators that guard this state.
            overrides = {**result.user_override, **accepted}
            result = JobAnalysis.model_validate(
                {**result.model_dump(mode="json"), "user_override": overrides}
            )

        # Checked before anything is written. An analysis whose Track, Profile,
        # and Emphasis disagree can never produce a draft, so persisting it would
        # only leave the application classified by a combination the engine
        # refuses to act on.
        selected_profile = AnalysisSelection.profile(result, profiles)
        plan_manifest = AnalysisSelection.manifest(result, knowledge)

        return PreparedAnalysis(
            result=result,
            plan_manifest=plan_manifest,
            provider=used_provider,
            model=used_model,
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": result.track.value,
                "emphasis": result.emphasis.value,
            },
            normalized_role=selected_profile.normalized_role,
            evidence=evidence,
            extraction_evidence=extraction_evidence,
        )

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
            # the user decided on: a Track change can remove a rule-derived gap,
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
        """§13, deterministic form: synchronous, and it returns the plan itself.

        No provider call happens inside a synchronous request, so this path
        never needs one. The AI `propose_selection_plan` mode is the same
        command's asynchronous form and arrives with the rest of the AI tasks.

        `repository` is the same escape `activate` takes: a caller that has to
        commit this plan together with something else binds its own UnitOfWork
        and passes the bound repository, so `apply_selection_change` gets one
        implementation of the overlay rather than a second copy of it.
        """
        self.load_active_application(command.application_id)
        repo = repository or self.repo
        record = self._analysis_record(command.application_id, command.job_analysis_id, repo)
        analysis: JobAnalysis = record["analysis"]
        try:
            latest_plan = repo.latest_selection_plan(command.application_id)
        except UnknownRecord:
            latest_plan = None
        active_plan = (
            latest_plan
            if latest_plan is not None and latest_plan.job_analysis_id == command.job_analysis_id
            else None
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
        knowledge = self.load_knowledge()
        self._refuse_moved_sources(command, knowledge)
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

    def prepare_selection_proposal(
        self,
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
        record = self._analysis_record(command.application_id, command.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]
        try:
            latest_plan = self.repo.latest_selection_plan(command.application_id)
        except UnknownRecord:
            latest_plan = None
        active_plan = (
            latest_plan
            if latest_plan is not None and latest_plan.job_analysis_id == command.job_analysis_id
            else None
        )
        effective_analysis = (
            analysis.model_copy(update={"emphasis": active_plan.plan.emphasis})
            if active_plan is not None
            else analysis
        )
        knowledge = self.load_knowledge()
        profile = AnalysisSelection.profile(effective_analysis, knowledge.profiles)
        allowed = allowed_fact_pool(profile)
        manifest = AnalysisSelection.manifest(effective_analysis, knowledge)

        answered = self.provider.propose_selection_plan(
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
        evidence = self.preserve(
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

    def activate_selection_proposal(
        self,
        prepared: PreparedSelectionProposal,
        repository: PreparationRepository | None = None,
    ) -> SelectionPlanResult:
        """Commit the proposed overlay through the deterministic command.

        Every check `create_selection_plan` makes runs again here, against
        Knowledge as it is at activation - not as it was when the provider was
        asked. That is the optimistic rule §13 requires, and it is why the AI
        path cannot commit a plan the deterministic path would have refused.
        """
        repo = repository or self.repo
        return self.create_selection_plan(prepared.command, repo)

    @staticmethod
    def _refuse_moved_sources(command: CreateSelectionPlanCommand, knowledge) -> None:
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

    def apply_analysis_decisions(
        self, command: ApplyAnalysisDecisionsCommand
    ) -> AnalysisDecisionsResult:
        """§13: one review-form submission, and the branch it actually takes.

        Meaning changed -> one new immutable JobAnalysis carrying the overrides,
        together with its initial deterministic SelectionPlan, committed
        atomically by `save_analysis`. Only Emphasis, fact selection, or gap
        acceptance changed -> one replacement SelectionPlan against the same
        analysis. Neither branch touches the records the user decided against.

        Accepting a hard gap is a *selection* decision, not a meaning one. It
        does not change what the requirement means, what it covers, or how it
        is classified - only that the user proceeds despite it - so it creates
        a replacement SelectionPlan and leaves the JobAnalysis alone. That also
        keeps one acceptance from re-deriving an analysis the user never asked
        to change.

        Accepting a low Fit is still an analysis-level override, and it now
        clears `LOW_FIT_REQUIRES_ACCEPTANCE` alone. It used to clear every hard
        gap with it, so one checkbox dismissed deficiencies the user had never
        been shown.

        Decisions accumulate. The submission is merged over the overrides the
        source analysis already carried, so a second decision does not silently
        drop the first, and withholding a field is not a retraction of it.
        """
        self.load_active_application(command.application_id)
        if command.expected_analysis_id != command.job_analysis_id:
            raise StateConflict(
                "the analysis addressed by the request does not match the analysis "
                "observed by the form"
            )
        record = self._analysis_record(command.application_id, command.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]

        candidates: dict[OverrideKey, str | None] = {
            "track": command.track_override,
            "profile": command.profile_override,
            "language": command.language_override,
        }
        submitted: dict[OverrideKey, str] = {
            key: value for key, value in candidates.items() if value
        }
        if command.accept_low_fit:
            submitted["fit"] = "accepted-low-fit"
        if command.accept_incomplete_analysis:
            submitted["analysis"] = ACCEPTED_INCOMPLETE_ANALYSIS
        merged = {**analysis.user_override, **submitted}
        active_plan: SelectionPlan | None = None
        if command.expected_selection_plan_id is not None:
            try:
                observed_plan = self.repo.selection_plan(command.expected_selection_plan_id)
            except UnknownRecord:
                observed_plan = None
            if (
                observed_plan is not None
                and observed_plan.application_id == command.application_id
                and observed_plan.job_analysis_id == command.job_analysis_id
            ):
                active_plan = observed_plan
        prior_emphasis_override = (
            active_plan.plan.emphasis_override if active_plan is not None else None
        )
        requested_emphasis_override = (
            Emphasis(command.emphasis_override) if command.emphasis_override is not None else None
        )
        emphasis_decision_changed = requested_emphasis_override is not None and (
            prior_emphasis_override != requested_emphasis_override
        )
        has_interpretation_corrections = bool(command.requirement_interpretations)
        previous_meaning = {
            key: value for key, value in analysis.user_override.items() if key != "emphasis"
        }
        submitted_meaning = {key: value for key, value in merged.items() if key != "emphasis"}
        changes_meaning = submitted_meaning != previous_meaning or has_interpretation_corrections
        has_fact_overlay = bool(command.pinned_fact_ids or command.excluded_fact_ids)
        has_overlay = bool(
            has_fact_overlay or command.accepted_requirement_ids or emphasis_decision_changed
        )

        # A plan-level Emphasis decision is folded into a newly-created
        # analysis only when another decision already requires that new
        # analysis. Otherwise the JobAnalysis stays immutable and only the
        # SelectionPlan changes.
        carried_emphasis = requested_emphasis_override or prior_emphasis_override
        if changes_meaning and carried_emphasis is not None:
            merged["emphasis"] = carried_emphasis.value

        if has_interpretation_corrections:
            # Stage-1 plan §3.5: a correction re-covers the named requirements
            # under their new interpretation and rebuilds gaps/Fit from the
            # result - it does not re-run classification or re-extract from
            # the provider, so it goes through its own path rather than
            # `self.analyze()`, which would do both.
            if has_fact_overlay:
                raise PreconditionFailed(
                    "a classification decision creates a new analysis with its own initial "
                    "SelectionPlan; apply the fact overlay to that analysis in a second command"
                )
            result = self._correct_interpretations(command, analysis, record, merged)
            return AnalysisDecisionsResult(
                application_id=command.application_id,
                job_analysis_id=result.analysis_id,
                selection_plan_id=result.selection_plan_id,
                created_analysis=True,
                analysis=result.analysis,
                plan=self.repo.selection_plan(result.selection_plan_id),
            )

        if changes_meaning and has_fact_overlay:
            # A classification decision produces a *new* analysis whose initial
            # plan is the deterministic one for that classification. Applying a
            # *fact* overlay to it would silently attach decisions the user made
            # about the old candidate accounting to a new one they have not seen.
            #
            # A gap acceptance is not that. It names a requirement rather than a
            # fact, requirement identity is keyed on the snapshot text rather
            # than on the classification, and it is re-checked against the new
            # analysis before it is stored - so it rides along, in the same
            # write, instead of being refused and re-submitted against a record
            # the user never asked to create.
            raise PreconditionFailed(
                "a classification decision creates a new analysis with its own initial "
                "SelectionPlan; apply the fact overlay to that analysis in a second command"
            )

        if changes_meaning:
            result = self._revise_classification(command, analysis, record, merged)
            return AnalysisDecisionsResult(
                application_id=command.application_id,
                job_analysis_id=result.analysis_id,
                selection_plan_id=result.selection_plan_id,
                created_analysis=True,
                analysis=result.analysis,
                plan=self.repo.selection_plan(result.selection_plan_id),
            )

        if not has_overlay:
            # Refused rather than answered with the plan that already exists: an
            # empty submission that created a second identical plan would put a
            # decision in the history that nobody made.
            raise PreconditionFailed("the submitted decisions change nothing")

        created = self.create_selection_plan(
            CreateSelectionPlanCommand(
                application_id=command.application_id,
                job_analysis_id=command.job_analysis_id,
                pinned_fact_ids=list(command.pinned_fact_ids),
                excluded_fact_ids=list(command.excluded_fact_ids),
                emphasis_override=(
                    requested_emphasis_override.value
                    if requested_emphasis_override is not None
                    else None
                ),
                accepted_requirement_ids=list(command.accepted_requirement_ids),
                acceptance_reason=command.acceptance_reason,
                expected_selection_plan_id=command.expected_selection_plan_id,
                enforce_expected_selection_plan=True,
                refuse_matching_context_operation=True,
            )
        )
        return AnalysisDecisionsResult(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            selection_plan_id=created.selection_plan_id,
            created_analysis=False,
            analysis=analysis,
            plan=created.plan,
        )

    def _revise_classification(
        self,
        command: ApplyAnalysisDecisionsCommand,
        analysis: JobAnalysis,
        record: dict,
        merged_overrides: dict[str, str],
    ) -> AnalysisResult:
        """Create a user-revised analysis without invoking an extractor or provider."""
        knowledge = self.load_knowledge()
        revised = revise_classification(analysis, merged_overrides, knowledge.profiles)
        selected = AnalysisSelection.profile(revised, knowledge.profiles)
        manifest = AnalysisSelection.manifest(revised, knowledge)
        return self.activate(
            AnalyzeCommand(
                application_id=command.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                accepted_requirement_ids=list(command.accepted_requirement_ids),
                acceptance_reason=command.acceptance_reason,
                expected_analysis_id=command.expected_analysis_id,
                expected_selection_plan_id=command.expected_selection_plan_id,
                refuse_matching_context_operation=True,
            ),
            PreparedAnalysis(
                result=revised,
                plan_manifest=manifest,
                provider="user",
                model="classification-correction-v1",
                candidate_context_version=knowledge.candidate.context_version,
                candidate_context_hash=knowledge.candidate.version_hash,
                profile_version=knowledge.profiles.version,
                selection_policy_version=knowledge.policies.version,
                track_emphasis_dependencies={
                    "track": revised.track.value,
                    "emphasis": revised.emphasis.value,
                },
                normalized_role=selected.normalized_role,
            ),
        )

    def _correct_interpretations(
        self,
        command: ApplyAnalysisDecisionsCommand,
        analysis: JobAnalysis,
        record: dict,
        merged_overrides: dict[str, str],
    ) -> AnalysisResult:
        """Stage-1 plan §3.5: re-cover the named requirements, not re-classify.

        Track, Profile, and Emphasis are untouched - a correction is a claim
        about what one requirement means, not a new classification. Every
        corrected interpretation passes the same interpretation gate a
        provider's original claim did, against the same signed snapshot text,
        so a correction cannot introduce a reading the gate would have refused
        from a provider.
        """
        snapshot = self.repo.get_snapshot(record["job_snapshot_id"])
        try:
            job_text = self.snapshot_payloads.read_snapshot(
                snapshot["payload_path"],
                snapshot["source_hash"],
            )
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        knowledge = self.load_knowledge()

        corrected_requirements, decisions = apply_interpretation_corrections(
            list(analysis.requirements),
            list(command.requirement_interpretations),
            source_text=job_text,
            normalized_hash=snapshot["normalized_hash"],
            facts=knowledge.facts,
            concepts=knowledge.requirement_concepts,
            actor=ACCEPTANCE_ACTOR,
            decided_at=utc_now(),
            prior_analysis_id=command.job_analysis_id,
        )
        rebased = rebase_requirements(
            analysis,
            requirements=corrected_requirements,
            extraction_version=analysis.extraction_version,
            facts=knowledge.facts,
            # A correction changes one requirement's interpretation, not
            # whether the extraction as a whole read the posting - that
            # signal is carried forward from the analysis being corrected
            # rather than re-derived, since only a fresh extraction run can
            # actually change it.
            extraction_failed="extraction-failed" in analysis.approval_reasons,
            # Same reasoning, same inheritance: whether the posting stated any
            # requirement, and whether one of its statements went unmapped, are
            # properties of the text. A correction does not re-read the text, so
            # neither can be re-derived here - only carried forward.
            requirements_absent="requirements-absent" in analysis.approval_reasons,
            requirements_unmapped="requirements-unmapped" in analysis.approval_reasons,
        )
        result = rebased.model_copy(
            update={
                "analysis_version": "2.0",
                "user_override": merged_overrides,
                "interpretation_decisions": [
                    *(analysis.interpretation_decisions or []),
                    *decisions,
                ],
            }
        )

        selected_profile = AnalysisSelection.profile(result, knowledge.profiles)
        plan_manifest = AnalysisSelection.manifest(result, knowledge)

        prepared = PreparedAnalysis(
            result=result,
            plan_manifest=plan_manifest,
            # Named truthfully rather than "deterministic": this record was
            # produced by a user's interpretation correction, not a fresh
            # deterministic classification run, and the two should not read
            # identically in history.
            provider="correction",
            model="interpretation-correction-v1",
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=knowledge.profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": result.track.value,
                "emphasis": result.emphasis.value,
            },
            normalized_role=selected_profile.normalized_role,
        )
        return self.activate(
            AnalyzeCommand(
                application_id=command.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                accepted_requirement_ids=list(command.accepted_requirement_ids),
                acceptance_reason=command.acceptance_reason,
                expected_analysis_id=command.expected_analysis_id,
                expected_selection_plan_id=command.expected_selection_plan_id,
                refuse_matching_context_operation=True,
            ),
            prepared,
        )
