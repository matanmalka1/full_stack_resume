from __future__ import annotations

import uuid
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
from ...util import normalized_text, sha256_file, sha256_text, utc_now
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

class ApplicationService(ServiceBase[ApplicationStore]):
    """Creating an application and its immutable job snapshot."""

    def ingest(self, command: IngestCommand) -> IngestedApplication:
        try:
            application_id = str(uuid.uuid4())
            snapshot_id = str(uuid.uuid4())
            payload = self.snapshot_payloads.commit_snapshot(
                application_id,
                snapshot_id,
                command.job_text,
            )
            application_id, snapshot_id = self.repo.create_application(
                company=command.company,
                target_role=command.target_role,
                payload_path=payload.reference,
                source_hash=payload.sha256,
                normalized_hash=sha256_text(normalized_text(command.job_text)),
                source_url=command.source_url,
                application_id=application_id,
                snapshot_id=snapshot_id,
            )
        except ValueError as exc:
            raise PreconditionFailed(str(exc)) from exc
        except OSError as exc:
            raise InfrastructureFailure(f"could not create application: {exc}") from exc
        return IngestedApplication(
            application_id=application_id,
            job_snapshot_id=snapshot_id,
        )
