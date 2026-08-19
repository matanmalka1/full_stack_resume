from __future__ import annotations

from dataclasses import dataclass

from ...domain.analysis.approval import merge_classification
from ...domain.analysis.classification import classify_job
from ...domain.models import (
    JobAnalysis,
    SelectionManifest,
)
from ...domain.selection import build_selection
from ..commands import (
    AnalysisResult,
    AnalyzeCommand,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ..ports import (
    PreparationRepository,
)
from .base import ServiceBase


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

    def prepare(self, command: AnalyzeCommand) -> PreparedAnalysis:
        """Validate and compute an analysis without mutating durable application state."""
        try:
            snapshot = self.repo.get_snapshot(command.job_snapshot_id)
        except KeyError as exc:
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
        if command.provider == "openai":
            if self._provider is None:
                raise DependencyUnavailable(
                    "AI classification was requested but no provider is configured"
                )
            # The provider sees the full deterministic picture as context, but it
            # answers on the narrower proposal contract; deterministic policy decides
            # what survives.
            proposal = self._provider.classify_job(
                {
                    "job_text": job_text,
                    "deterministic_classification": {
                        "track": deterministic.track.value,
                        "profile": deterministic.profile.value,
                        "emphasis": deterministic.emphasis.value,
                        "confidence": deterministic.confidence,
                        "language": deterministic.language,
                    },
                    "deterministic_gaps": [
                        gap.model_dump(mode="json") for gap in deterministic.gaps
                    ],
                    "overrides": deterministic.user_override,
                },
                model=command.model,
            )
            result = merge_classification(deterministic, proposal, profiles)
            used_provider, used_model = "openai", command.model
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
        try:
            selected_profile = profiles.get(result.profile)
        except (KeyError, ValueError) as exc:
            raise PreconditionFailed(f"analysis selected an unavailable Profile: {exc}") from exc
        if result.track is not selected_profile.track:
            raise StateConflict(
                f"classified Track {result.track.value} and Profile {result.profile.value} "
                f"are inconsistent: {result.profile.value} belongs to Track "
                f"{selected_profile.track.value}"
            )
        if result.emphasis not in selected_profile.allowed_emphases:
            raise StateConflict(
                f"Emphasis {result.emphasis.value} is not allowed for Profile "
                f"{result.profile.value}"
            )

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
