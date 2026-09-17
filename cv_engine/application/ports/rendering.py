from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...domain.contracts.records import ApprovedRevision
from ...domain.contracts.selection import SelectionPlan
from .transactions import ReadTransaction


@dataclass(frozen=True)
class RenderOperationSources:
    revision: ApprovedRevision
    manifest: dict[str, Any]
    snapshot: dict[str, Any]
    analysis: dict[str, Any]
    plan: SelectionPlan
    decision: dict[str, Any]
    latest_snapshot_id: str
    analyses: tuple[dict[str, Any], ...]


class RenderContextReader(Protocol):
    def application_deleted_at(self, tx: ReadTransaction, application_id: str) -> str | None: ...
    def operation_sources(
        self, tx: ReadTransaction, revision_id: str
    ) -> RenderOperationSources: ...
    def matching_render_artifact(
        self,
        tx: ReadTransaction,
        revision_id: str,
        artifact_type: str,
        content_hash: str,
        lifecycle_status: str,
    ) -> dict[str, Any] | None: ...
