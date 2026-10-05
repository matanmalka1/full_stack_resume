"""Ports: what the application layer needs from the outside, as protocols.

Capabilities follow real consumer, lifecycle, and trust boundaries.
"""

from .application_intake import (
    AuditLogWriter,
    InitialRecruitmentEventWriter,
    IntakeApplicationStore,
)
from .application_projections import ApplicationProjectionReader
from .knowledge_lifecycle import KnowledgeLifecycleStore
from .operation_client import OperationClientStore
from .operation_execution import OperationExecutionStore
from .outbound import (
    AIAttempt,
    AIProvider,
    AnalysisContext,
    AssessClaimSupportContext,
    DraftResumeContext,
    KnowledgeStore,
    PayloadInventory,
    PayloadVerifier,
    RegenerateClaimContext,
    RegenerateSectionContext,
    Renderer,
)
from .settings import SettingsRepository, SettingsStore
from .transactions import ReadTransaction, TransactionManager, WriteTransaction
from .values import (
    ArtifactStream,
    PayloadReference,
    TaskContract,
    TaskContracts,
)

__all__ = [
    "AIAttempt",
    "AssessClaimSupportContext",
    "AnalysisContext",
    "AIProvider",
    "AuditLogWriter",
    "ApplicationProjectionReader",
    "ArtifactStream",
    "DraftResumeContext",
    "KnowledgeLifecycleStore",
    "KnowledgeStore",
    "InitialRecruitmentEventWriter",
    "IntakeApplicationStore",
    "OperationClientStore",
    "OperationExecutionStore",
    "PayloadReference",
    "PayloadVerifier",
    "RegenerateClaimContext",
    "RegenerateSectionContext",
    "Renderer",
    "ReadTransaction",
    "PayloadInventory",
    "SettingsRepository",
    "SettingsStore",
    "TaskContract",
    "TaskContracts",
    "TransactionManager",
    "WriteTransaction",
]
