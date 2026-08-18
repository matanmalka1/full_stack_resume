from __future__ import annotations

from typing import Any, Generic, TypeVar

from ... import __version__
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

class ApplicationQueryService(ServiceBase[QueryRepository]):
    """Storage-neutral read projections for CLI, API, and future UI clients."""

    def list_applications(self) -> ApplicationListView:
        try:
            return ApplicationListView(
                items=[application_view(row) for row in self.repo.list_applications()]
            )
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(
                f"stored application projection is invalid: {exc}"
            ) from exc

    def application_detail(self, application_id: str) -> ApplicationDetailView:
        try:
            application = application_view(self.repo.get_application(application_id))
            snapshot = snapshot_view(self.repo.latest_snapshot(application_id))
            analyses = self.repo.analyses(application_id)
            latest = analysis_view(analyses[-1]) if analyses else None
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(
                f"stored application detail is invalid: {exc}"
            ) from exc
        return ApplicationDetailView(
            application=application,
            latest_snapshot=snapshot,
            latest_analysis=latest,
        )

    def artifact_versions(self, application_id: str) -> ArtifactVersionsView:
        try:
            self.repo.get_application(application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        try:
            return ArtifactVersionsView(
                items=[
                    artifact_version_view(row)
                    for row in self.repo.artifact_versions(application_id)
                ]
            )
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(
                f"stored artifact projection is invalid: {exc}"
            ) from exc

    def latest_decision(self, application_id: str) -> DecisionRecordView:
        try:
            return decision_view(self.repo.latest_decision(application_id))
        except KeyError as exc:
            raise UnknownRecord(
                f"no decision record for application: {application_id}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(
                f"stored decision projection is invalid: {exc}"
            ) from exc
