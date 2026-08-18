from __future__ import annotations

from typing import Any, Generic, TypeVar

from ... import __version__
from ...domain.analysis import classify_job, merge_classification, unresolved_approval_reasons
from ...domain.drafts import (
    apply_claim_edit,
    build_draft,
    serialize_markdown,
    synchronize_markdown_claims,
)
from ...domain.facts import FactStore, FactStoreError
from ...domain.knowledge import Knowledge
from ...domain.models import (
    ApplicationStatus,
    CandidateContext,
    DraftDocument,
    Fact,
    FactStatus,
    JobAnalysis,
    ValidationReport,
)
from ...domain.profiles import ProfileStore
from ...domain.selection import EmphasisPolicyStore
from ...domain.validation import validate_draft
from ...util import sha256_file, utc_now
from ..chain import ChainError, check_draft_chain, decision_record_analysis_id
from ..commands import (
    AnalyzeCommand,
    AnalysisResult,
    ApplicationMutationResult,
    ApprovalResult,
    DraftCommand,
    DraftResult,
    EditResult,
    FactAttachmentResult,
    FactDetailResult,
    FactHistoryResult,
    FactListItem,
    FactListResult,
    FactMutationResult,
    FactReconciliationResult,
    IngestCommand,
    IngestedApplication,
    KnowledgeVersionsResult,
    NextActionCommand,
    RecruitmentStatusCommand,
    RenderResult,
    SubmissionResult,
    fact_event_view,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
    WorkflowError,
)
from ..ports import (
    ApplicationStore,
    ArtifactStore,
    ClassificationProvider,
    DraftRepository,
    KnowledgeAuditRepository,
    KnowledgeStore,
    PreparationRepository,
    QueryRepository,
    ReadinessRepository,
    Renderer,
    TrackingRepository,
)
from ..queries import (
    ApplicationDetailView,
    ApplicationListView,
    ArtifactVersionsView,
    DecisionRecordView,
    analysis_view,
    application_view,
    artifact_version_view,
    decision_view,
    snapshot_view,
)
from ..ready import verify_ready_integrity


RepoT = TypeVar("RepoT")



from .base import ServiceBase

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
            deterministic = classify_job(
                snapshot["original_text"],
                track_override=command.track_override,
                profile_override=command.profile_override,
                emphasis_override=command.emphasis_override,
                language_override=command.language_override,
            )
        except ValueError as exc:
            raise PreconditionFailed(f"invalid analysis request: {exc}") from exc
        result = deterministic
        used_provider, used_model = "deterministic", "rules-v1"
        _, profiles, _ = self.knowledge()
        if command.provider == "openai":
            if self._provider is None:
                raise DependencyUnavailable("AI classification was requested but no provider is configured")
            # The provider sees the full deterministic picture as context, but it
            # answers on the narrower proposal contract; deterministic policy decides
            # what survives.
            proposal = self._provider.classify_job(
                {
                    "job_text": snapshot["original_text"],
                    "deterministic_classification": {
                        "track": deterministic.track.value,
                        "profile": deterministic.profile.value,
                        "emphasis": deterministic.emphasis.value,
                        "confidence": deterministic.confidence,
                        "language": deterministic.language,
                    },
                    "deterministic_gaps": [gap.model_dump(mode="json") for gap in deterministic.gaps],
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
            result = JobAnalysis.model_validate({**result.model_dump(mode="json"), "user_override": overrides})

        # Checked before anything is written. An analysis whose Track, Profile,
        # and Emphasis disagree can never produce a draft, so persisting it would
        # only leave the application classified by a combination the engine
        # refuses to act on.
        try:
            selected_profile = profiles.get(result.profile)
        except (KeyError, ValueError) as exc:
            raise PreconditionFailed(
                f"analysis selected an unavailable Profile: {exc}"
            ) from exc
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

        analysis_id = self.repo.save_analysis(
            command.application_id,
            snapshot["id"],
            result,
            provider=used_provider,
            model=used_model,
        )
        self.repo.set_normalized_role(command.application_id, selected_profile.normalized_role)
        return AnalysisResult(
            application_id=command.application_id,
            job_snapshot_id=command.job_snapshot_id,
            analysis_id=analysis_id,
            analysis=result,
        )
