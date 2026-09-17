from __future__ import annotations

from typing import Any

from ...domain.contracts.records import ValidationRunLineage
from ...domain.contracts.validation import ValidationReport
from .artifacts_sql import (
    _artifact_version,
    _artifact_version_for_revision,
    _artifact_versions,
    _decision_for_artifact_version,
    _decision_for_revision,
    _latest_artifact_version,
    _latest_decision,
    _latest_validation_for_working_draft,
    _record_validation,
    _register_artifact_version,
    _validation_for_artifact,
    _validation_lineage,
    _validation_report,
    _validation_run,
)
from .base import SqlAlchemyRepositoryBase


class SqlAlchemyArtifactRepository(SqlAlchemyRepositoryBase):
    def register_artifact_version(
        self,
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
    ) -> str:
        with self.transaction() as connection:
            return _register_artifact_version(
                connection,
                application_id,
                artifact_type,
                logical_name,
                path,
                content_hash,
                lifecycle_status,
                revision_id=revision_id,
                job_snapshot_id=job_snapshot_id,
                track=track,
                profile=profile,
                emphasis=emphasis,
                facts_version=facts_version,
                metadata=metadata,
                approved_at=approved_at,
                submitted_at=submitted_at,
                artifact_version_id=artifact_version_id,
            )

    def latest_artifact_version(
        self, application_id: str, artifact_type: str, lifecycle_status: str | None = None
    ) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _latest_artifact_version(
                connection, application_id, artifact_type, lifecycle_status
            )

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            return _artifact_versions(connection, application_id)

    def artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _artifact_version(connection, artifact_version_id)

    def artifact_version_for_revision(
        self, revision_id: str, artifact_type: str, lifecycle_status: str | None = None
    ) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _artifact_version_for_revision(
                connection, revision_id, artifact_type, lifecycle_status
            )

    def latest_decision(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _latest_decision(connection, application_id)

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _decision_for_artifact_version(connection, artifact_version_id)

    def decision_for_revision(self, revision_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _decision_for_revision(connection, revision_id)

    def record_validation(
        self,
        application_id: str,
        phase: str,
        report: ValidationReport,
        artifact_version_id: str | None = None,
        *,
        lineage: ValidationRunLineage | None = None,
    ) -> str:
        with self.transaction() as connection:
            return _record_validation(
                connection, application_id, phase, report, artifact_version_id, lineage=lineage
            )

    def validation_lineage(self, validation_id: str) -> ValidationRunLineage:
        with self.read_connection() as connection:
            return _validation_lineage(connection, validation_id)

    def latest_validation_for_working_draft(self, working_draft_id: str) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            return _latest_validation_for_working_draft(connection, working_draft_id)

    def validation_for_artifact(
        self, application_id: str, phase: str, artifact_version_id: str
    ) -> ValidationReport:
        with self.read_connection() as connection:
            return _validation_for_artifact(connection, application_id, phase, artifact_version_id)

    def validation_report(self, validation_id: str) -> ValidationReport:
        with self.read_connection() as connection:
            return _validation_report(connection, validation_id)

    def validation_run(self, validation_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            return _validation_run(connection, validation_id)
