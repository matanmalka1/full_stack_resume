from __future__ import annotations

from dataclasses import dataclass

from ...domain.analysis.approval import merge_classification
from ...domain.analysis.classification import classify_job
from ...domain.models import (
    JobAnalysis,
    OverrideKey,
    Profile,
    SelectionManifest,
    SelectionProposal,
)
from ...domain.profiles import ProfileStore
from ...domain.selection import build_selection
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
    # Re-exported: the CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ..ports import (
    JobAnalysisContext,
    PreparationRepository,
    SelectionPlanContext,
)
from .base import ServiceBase
from .proposals import (
    ProviderEvidence,
    allowed_fact_pool,
    evidence_attached,
    fact_context,
    refuse_facts_outside_the_pool,
)


@dataclass(frozen=True)
class PreparedAnalysis:
    result: JobAnalysis
    plan_manifest: SelectionManifest
    provider: str
    model: str
    candidate_context_version: str
    candidate_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    normalized_role: str
    evidence: ProviderEvidence | None = None


@dataclass(frozen=True)
class PreparedSelectionProposal:
    """An AI `propose_selection_plan` result, reduced to a deterministic command.

    The Proposal never becomes a plan directly. It becomes the same overlay a
    user's review form submits, and activation runs `create_selection_plan`
    over it - so the plan that lands passed the identical Profile, allowed-fact,
    budget, and optimistic-source checks a deterministic plan passes (§13).
    """

    command: CreateSelectionPlanCommand
    proposal: SelectionProposal
    evidence: ProviderEvidence


class AnalysisService(ServiceBase[PreparationRepository]):
    """Classification, fit, and the analysis record."""

    def analyze(
        self,
        command: AnalyzeCommand,
    ) -> AnalysisResult:
        """Classify one exact job snapshot.

        The snapshot is named by the caller. `latest` is a query convenience
        and belongs to the compatibility layer, not to a command: a command
        that picks its own source can silently analyse something other than
        what the caller was looking at.
        """
        prepared = self.prepare(command)
        return self.activate(command, prepared)

    @staticmethod
    def _consistent_profile(analysis: JobAnalysis, profiles: ProfileStore) -> Profile:
        """The Profile this classification names, or the refusal that it disagrees.

        A Track, Profile, and Emphasis that disagree can never produce a draft,
        so the combination is refused wherever it is about to be acted on rather
        than only where it is about to be written.
        """
        try:
            selected = profiles.get(analysis.profile)
        except (KeyError, ValueError) as exc:
            raise PreconditionFailed(f"analysis selected an unavailable Profile: {exc}") from exc
        if analysis.track is not selected.track:
            raise StateConflict(
                f"classified Track {analysis.track.value} and Profile "
                f"{analysis.profile.value} are inconsistent: {analysis.profile.value} "
                f"belongs to Track {selected.track.value}"
            )
        if analysis.emphasis not in selected.allowed_emphases:
            raise StateConflict(
                f"Emphasis {analysis.emphasis.value} is not allowed for Profile "
                f"{analysis.profile.value}"
            )
        return selected

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
        try:
            deterministic = classify_job(
                job_text,
                track_override=command.track_override,
                profile_override=command.profile_override,
                emphasis_override=command.emphasis_override,
                language_override=command.language_override,
            )
        except ValueError as exc:
            raise PreconditionFailed(f"invalid analysis request: {exc}") from exc
        result = deterministic
        used_provider, used_model = "deterministic", "rules-v1"
        knowledge = self.load_knowledge()
        profiles = knowledge.profiles
        evidence: ProviderEvidence | None = None
        if command.provider == "openai":
            if operation_id is None:
                raise PreconditionFailed(
                    "AI analysis runs as an Operation; there is no synchronous form"
                )
            # The provider sees the full deterministic picture as context, but it
            # answers on the narrower proposal contract; deterministic policy decides
            # what survives.
            answered = self.provider.propose_job_analysis(
                JobAnalysisContext(
                    job_text=job_text,
                    deterministic_classification={
                        "track": deterministic.track.value,
                        "profile": deterministic.profile.value,
                        "emphasis": deterministic.emphasis.value,
                        "confidence": deterministic.confidence,
                        "language": deterministic.language,
                    },
                    deterministic_gaps=[gap.model_dump(mode="json") for gap in deterministic.gaps],
                    overrides={
                        str(key): value for key, value in deterministic.user_override.items()
                    },
                )
            )
            evidence = self.preserve(
                command.application_id, operation_id, "propose_job_analysis", answered.provenance
            )
            result = merge_classification(deterministic, answered.proposal, profiles)
            used_provider = answered.provenance.context.provider
            used_model = answered.provenance.context.model
        elif command.provider != "deterministic":
            raise DependencyUnavailable(f"unsupported provider: {command.provider}")

        if command.accept_low_fit:
            # Rebuilt through validation rather than model_copy(update=...), which
            # would skip the model validators that guard this state.
            overrides = {**result.user_override, "fit": "accepted-low-fit"}
            result = JobAnalysis.model_validate(
                {**result.model_dump(mode="json"), "user_override": overrides}
            )

        # Checked before anything is written. An analysis whose Track, Profile,
        # and Emphasis disagree can never produce a draft, so persisting it would
        # only leave the application classified by a combination the engine
        # refuses to act on.
        selected_profile = self._consistent_profile(result, profiles)

        try:
            _, plan_manifest = build_selection(
                analysis=result,
                profile=selected_profile,
                policy=knowledge.policies.get(result.emphasis),
                policy_store_version=knowledge.policies.version,
                facts=knowledge.facts,
                line_groups=(
                    knowledge.presentations.line_groups(selected_profile, result.emphasis)
                    if knowledge.presentations is not None
                    else None
                ),
            )
        except ValueError as exc:
            raise PreconditionFailed(f"selection plan could not be built: {exc}") from exc

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
        repo = repository or self.repo
        record = self._analysis_record(command.application_id, command.job_analysis_id, repo)
        analysis: JobAnalysis = record["analysis"]
        knowledge = self.load_knowledge()
        self._refuse_moved_sources(command, knowledge)
        selected_profile = self._consistent_profile(analysis, knowledge.profiles)
        try:
            _, manifest = build_selection(
                analysis=analysis,
                profile=selected_profile,
                policy=knowledge.policies.get(analysis.emphasis),
                policy_store_version=knowledge.policies.version,
                facts=knowledge.facts,
                line_groups=(
                    knowledge.presentations.line_groups(selected_profile, analysis.emphasis)
                    if knowledge.presentations is not None
                    else None
                ),
                pinned_fact_ids=frozenset(command.pinned_fact_ids),
                excluded_fact_ids=frozenset(command.excluded_fact_ids),
            )
        except ValueError as exc:
            raise PreconditionFailed(f"selection plan could not be built: {exc}") from exc
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
                "emphasis": analysis.emphasis.value,
            },
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
        knowledge = self.load_knowledge()
        profile = self._consistent_profile(analysis, knowledge.profiles)
        allowed = allowed_fact_pool(profile)
        deterministic, manifest = self._deterministic_selection(analysis, profile, knowledge)
        del deterministic

        answered = self.provider.propose_selection_plan(
            SelectionPlanContext(
                job_analysis={
                    "track": analysis.track.value,
                    "profile": analysis.profile.value,
                    "emphasis": analysis.emphasis.value,
                    "language": analysis.language,
                    "keywords": list(analysis.keywords),
                    "gaps": [gap.model_dump(mode="json") for gap in analysis.gaps],
                },
                allowed_facts=fact_context(knowledge.facts, sorted(allowed), analysis.language),
                deterministic_selection={
                    "selected_fact_ids": list(manifest.selected_fact_ids),
                    "emphasis_policy_version": manifest.emphasis_policy_version,
                },
            )
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
                expected_candidate_context_hash=command.expected_candidate_context_hash,
                expected_profile_version=command.expected_profile_version,
                expected_selection_policy_version=command.expected_selection_policy_version,
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

    def _deterministic_selection(self, analysis: JobAnalysis, profile: Profile, knowledge):
        """The plan the rules would build, as context for a proposal.

        Shared with nothing else on purpose: it is context, not a commit. The
        plan that lands is built again at activation from current Knowledge.
        """
        try:
            return build_selection(
                analysis=analysis,
                profile=profile,
                policy=knowledge.policies.get(analysis.emphasis),
                policy_store_version=knowledge.policies.version,
                facts=knowledge.facts,
                line_groups=(
                    knowledge.presentations.line_groups(profile, analysis.emphasis)
                    if knowledge.presentations is not None
                    else None
                ),
            )
        except ValueError as exc:
            raise PreconditionFailed(f"selection plan could not be built: {exc}") from exc

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
        atomically by `save_analysis`. Only the fact overlay changed -> one
        replacement SelectionPlan against the same analysis. Neither branch
        touches the analysis or plan the user decided against; both remain
        readable history.

        Accepting a low Fit or a hard gap is a meaning decision, not a selection
        one: the acceptance is recorded as the analysis override that the state
        projection already reads to clear `LOW_FIT_REQUIRES_ACCEPTANCE` and
        `HARD_GAP_REQUIRES_DECISION`. There is no second place that records it.

        Decisions accumulate. The submission is merged over the overrides the
        source analysis already carried, so a second decision does not silently
        drop the first, and withholding a field is not a retraction of it.
        """
        record = self._analysis_record(command.application_id, command.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]

        candidates: dict[OverrideKey, str | None] = {
            "track": command.track_override,
            "profile": command.profile_override,
            "emphasis": command.emphasis_override,
            "language": command.language_override,
        }
        submitted: dict[OverrideKey, str] = {
            key: value for key, value in candidates.items() if value
        }
        if command.accept_low_fit:
            submitted["fit"] = "accepted-low-fit"
        merged = {**analysis.user_override, **submitted}
        changes_meaning = merged != dict(analysis.user_override)
        has_overlay = bool(command.pinned_fact_ids or command.excluded_fact_ids)

        if changes_meaning and has_overlay:
            # A classification decision produces a *new* analysis whose initial
            # plan is the deterministic one for that classification. Applying
            # this overlay to it would silently attach decisions the user made
            # about the old candidate accounting to a new one they have not seen.
            raise PreconditionFailed(
                "a classification decision creates a new analysis with its own initial "
                "SelectionPlan; apply the fact overlay to that analysis in a second command"
            )

        if changes_meaning:
            # Deterministic re-derivation under the user's overrides. The new
            # record names `deterministic` as its provider truthfully: it is
            # what produced it, whatever produced the analysis being decided on.
            result = self.analyze(
                AnalyzeCommand(
                    application_id=command.application_id,
                    job_snapshot_id=record["job_snapshot_id"],
                    track_override=merged.get("track"),
                    profile_override=merged.get("profile"),
                    emphasis_override=merged.get("emphasis"),
                    language_override=merged.get("language"),
                    accept_low_fit=merged.get("fit") == "accepted-low-fit",
                )
            )
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
