"""Ports: what the application layer needs from the outside, as protocols.

Split into modules by what a name is, not by who imports it: `values` for
what crosses a boundary, `outbound` for effects the application cannot
perform itself, `repositories` for one stored capability each, and the
`composed_*` modules for the unions a service or the composition root
receives - themselves split by domain (prep / tracking / knowledge / shared),
matching how `commands/` and `infrastructure/persistence/tables/` are split.

Re-exported here so importers name one place, as they did when this was a
single 789-line module.
"""

from .application_intake import (
    AuditLogWriter,
    InitialRecruitmentEventWriter,
    IntakeApplicationStore,
    JobSnapshotStore,
)
from .composed_knowledge import KnowledgeAuditRepository
from .composed_prep import DraftRepository, ReadinessRepository
from .composed_shared import ApplicationRepository, QueryRepository
from .composed_tracking import TrackingRepository
from .outbound import (
    AIProposal,
    AIProvider,
    AnalysisContext,
    ArtifactStore,
    DraftResumeContext,
    KnowledgeStore,
    RegenerateClaimContext,
    RegenerateSectionContext,
    Renderer,
    RevisionPayloadStore,
    SelectionPlanContext,
    SnapshotPayloadStore,
)
from .repositories import (
    ApplicationStore,
    ArtifactRegistry,
    FactAudit,
    JobStore,
    KnowledgeMutationRepository,
    OperationRepository,
    UnitOfWork,
    WorkingDraftReader,
)
from .transactions import ReadTransaction, TransactionManager, WriteTransaction
from .values import (
    ArtifactStream,
    DraftPaths,
    RenderTargets,
    RevisionPayloads,
    SnapshotPayload,
    StoredDraft,
    TaskContract,
    TaskContracts,
)

__all__ = [
    "AIProposal",
    "AnalysisContext",
    "AIProvider",
    "AuditLogWriter",
    "ApplicationRepository",
    "ApplicationStore",
    "ArtifactRegistry",
    "ArtifactStore",
    "ArtifactStream",
    "DraftPaths",
    "DraftResumeContext",
    "DraftRepository",
    "FactAudit",
    "JobStore",
    "KnowledgeAuditRepository",
    "KnowledgeMutationRepository",
    "KnowledgeStore",
    "InitialRecruitmentEventWriter",
    "IntakeApplicationStore",
    "JobSnapshotStore",
    "OperationRepository",
    "QueryRepository",
    "ReadinessRepository",
    "RegenerateClaimContext",
    "RegenerateSectionContext",
    "RenderTargets",
    "Renderer",
    "ReadTransaction",
    "RevisionPayloadStore",
    "RevisionPayloads",
    "SelectionPlanContext",
    "SnapshotPayload",
    "SnapshotPayloadStore",
    "StoredDraft",
    "TaskContract",
    "TaskContracts",
    "TrackingRepository",
    "TransactionManager",
    "UnitOfWork",
    "WorkingDraftReader",
    "WriteTransaction",
]
