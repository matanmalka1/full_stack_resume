from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction, WriteTransaction


class ArtifactCatalog(Protocol):
    def register_artifact_version(
        self,
        tx: WriteTransaction,
        application_id: str | None,
        artifact_type: str,
        logical_name: str,
        path: str,
        content_hash: str,
        lifecycle_status: str,
        *,
        revision_id: str | None = None,
        job_snapshot_id: str | None = None,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        facts_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        approved_at: str | None = None,
        submitted_at: str | None = None,
        artifact_version_id: str | None = None,
    ) -> str: ...

    def latest_artifact_version(
        self,
        tx: ReadTransaction,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]: ...

    def artifact_versions(
        self, tx: ReadTransaction, application_id: str
    ) -> list[dict[str, Any]]: ...

    def artifact_version(self, tx: ReadTransaction, artifact_version_id: str) -> dict[str, Any]: ...

    def artifact_version_for_revision(
        self,
        tx: ReadTransaction,
        revision_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]: ...
