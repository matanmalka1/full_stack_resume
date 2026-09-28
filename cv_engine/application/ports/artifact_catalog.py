from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction


class ArtifactCatalog(Protocol):
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
