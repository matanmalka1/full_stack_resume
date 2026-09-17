"""Ports: what the application layer needs from the outside, as protocols.

Capabilities follow real consumer, lifecycle, and trust boundaries.
"""

from .application_intake import (
    AuditLogWriter,
    InitialRecruitmentEventWriter,
    IntakeApplicationStore,
    JobSnapshotStore,
)
from .application_projections import ApplicationProjectionReader
from .knowledge_lifecycle import KnowledgeLifecycleStore
from .operation_client import OperationClientStore
from .operation_execution import OperationExecutionStore
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
from .settings import SettingsStore
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
    "ApplicationProjectionReader",
    "ArtifactStore",
    "ArtifactStream",
    "DraftPaths",
    "DraftResumeContext",
    "KnowledgeLifecycleStore",
    "KnowledgeStore",
    "InitialRecruitmentEventWriter",
    "IntakeApplicationStore",
    "JobSnapshotStore",
    "OperationClientStore",
    "OperationExecutionStore",
    "RegenerateClaimContext",
    "RegenerateSectionContext",
    "RenderTargets",
    "Renderer",
    "ReadTransaction",
    "RevisionPayloadStore",
    "RevisionPayloads",
    "SelectionPlanContext",
    "SettingsStore",
    "SnapshotPayload",
    "SnapshotPayloadStore",
    "StoredDraft",
    "TaskContract",
    "TaskContracts",
    "TransactionManager",
    "WriteTransaction",
]
