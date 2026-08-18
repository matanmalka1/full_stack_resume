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

class TrackingService(ServiceBase[TrackingRepository]):
    """Recruitment-side state: submission and its evidence."""

    def transition_status(
        self, command: RecruitmentStatusCommand
    ) -> ApplicationMutationResult:
        try:
            self.repo.transition_status(
                command.application_id, command.target_status, command.reason
            )
            application = self.repo.get_application(command.application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        return ApplicationMutationResult(
            application_id=command.application_id,
            current_status=application["current_status"],
            next_action=application.get("next_action"),
            next_action_date=application.get("next_action_date"),
        )

    def set_next_action(self, command: NextActionCommand) -> ApplicationMutationResult:
        try:
            self.repo.set_next_action(
                command.application_id,
                command.next_action,
                command.next_action_date,
            )
            application = self.repo.get_application(command.application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        return ApplicationMutationResult(
            application_id=command.application_id,
            current_status=application["current_status"],
            next_action=application.get("next_action"),
            next_action_date=application.get("next_action_date"),
        )

    def submit(self, application_id: str, reason: str = "submitted to employer") -> SubmissionResult:
        try:
            application = self.repo.get_application(application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        if application["current_status"] != ApplicationStatus.READY.value:
            raise StateConflict("applied requires a currently valid ready application")
        integrity = verify_ready_integrity(self.artifacts, self._knowledge, self.repo, application_id)
        if not integrity.passed:
            raise ValidationBlocked(
                "applied blocked by stale or tampered ready state: "
                f"{[issue.code for issue in integrity.issues]}"
            )
        pdf_artifact_version_id = integrity.evidence["pdf_artifact_version_id"]
        self.repo.record_submission(application_id, pdf_artifact_version_id, reason)
        updated = self.repo.get_application(application_id)
        return SubmissionResult(
            application_id=application_id,
            pdf_artifact_version_id=pdf_artifact_version_id,
            current_status=updated["current_status"],
            next_action=updated.get("next_action"),
            next_action_date=updated.get("next_action_date"),
        )
