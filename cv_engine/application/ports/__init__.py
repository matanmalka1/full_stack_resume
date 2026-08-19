"""Ports: what the application layer needs from the outside, as protocols.

Split into four modules by what a name is, not by who imports it: `values`
for what crosses a boundary, `outbound` for effects the application cannot
perform itself, `repositories` for one stored capability each, and
`composed` for the unions a service or the composition root receives.

Re-exported here so importers name one place, as they did when this was a
single 789-line module.
"""

from .composed import (
    ApplicationRepository,
    DraftRepository,
    KnowledgeAuditRepository,
    PreparationRepository,
    QueryRepository,
    ReadinessRepository,
    TrackingRepository,
)
from .outbound import (
    ArtifactStore,
    ClassificationProvider,
    KnowledgeStore,
    Renderer,
    RevisionPayloadStore,
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
from .values import (
    DraftPaths,
    RenderTargets,
    RevisionPayloads,
    SnapshotPayload,
    StoredDraft,
)

__all__ = [
    "ApplicationRepository",
    "ApplicationStore",
    "ArtifactRegistry",
    "ArtifactStore",
    "ClassificationProvider",
    "DraftPaths",
    "DraftRepository",
    "FactAudit",
    "JobStore",
    "KnowledgeAuditRepository",
    "KnowledgeMutationRepository",
    "KnowledgeStore",
    "OperationRepository",
    "PreparationRepository",
    "QueryRepository",
    "ReadinessRepository",
    "RenderTargets",
    "Renderer",
    "RevisionPayloadStore",
    "RevisionPayloads",
    "SnapshotPayload",
    "SnapshotPayloadStore",
    "StoredDraft",
    "TrackingRepository",
    "UnitOfWork",
    "WorkingDraftReader",
]
