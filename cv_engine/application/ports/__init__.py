"""Ports: what the application layer needs from the outside, as protocols.

Capabilities follow real consumer, lifecycle, and trust boundaries.
"""

from .application_intake import (
    AuditLogWriter,
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
    FactFromAnswerContext,
    GapQuestionsContext,
    KnowledgeStore,
    RegenerateClaimContext,
    RegenerateSectionContext,
    Renderer,
)
from .settings import SettingsRepository, SettingsStore
from .transactions import ReadTransaction, TransactionManager, WriteTransaction
from .values import (
    ArtifactStream,
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
    "FactFromAnswerContext",
    "GapQuestionsContext",
    "KnowledgeLifecycleStore",
    "KnowledgeStore",
    "IntakeApplicationStore",
    "OperationClientStore",
    "OperationExecutionStore",
    "RegenerateClaimContext",
    "RegenerateSectionContext",
    "Renderer",
    "ReadTransaction",
    "SettingsRepository",
    "SettingsStore",
    "TaskContract",
    "TaskContracts",
    "TransactionManager",
    "WriteTransaction",
]
