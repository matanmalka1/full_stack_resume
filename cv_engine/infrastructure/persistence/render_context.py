from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.ports.rendering import RenderOperationSources
from ...application.ports.transactions import ReadTransaction
from .analysis_sql import _analysis_record, _selection_plan_record
from .artifacts_sql import _artifact_version_for_revision, _decision_for_revision
from .connection import SqlAlchemyTransactionManager
from .drafts_sql import _approved_revision
from .preparation import _snapshot_record
from .tables import (
    applications,
    artifact_versions,
    artifacts,
    job_analyses,
    job_snapshots,
    selection_plans,
)


class SqlAlchemyRenderContextReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def application_deleted_at(self, tx: ReadTransaction, application_id: str) -> str | None:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(applications.c.deleted_at).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return row["deleted_at"]

    def operation_sources(self, tx: ReadTransaction, revision_id: str) -> RenderOperationSources:
        connection = self._transactions.connection_for(tx)
        revision = _approved_revision(connection, revision_id)
        manifest = _artifact_version_for_revision(
            connection, revision_id, "claim_manifest", "approved"
        )
        snapshot_row = (
            connection.execute(
                select(job_snapshots).where(job_snapshots.c.id == revision.job_snapshot_id)
            )
            .mappings()
            .one_or_none()
        )
        analysis_row = (
            connection.execute(
                select(job_analyses).where(job_analyses.c.id == revision.job_analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        plan_row = (
            connection.execute(
                select(selection_plans).where(selection_plans.c.id == revision.selection_plan_id)
            )
            .mappings()
            .one_or_none()
        )
        if snapshot_row is None or analysis_row is None or plan_row is None:
            raise UnknownRecord("render source is missing")
        analysis_rows = (
            connection.execute(
                select(job_analyses)
                .where(job_analyses.c.application_id == revision.application_id)
                .order_by(job_analyses.c.version_number)
            )
            .mappings()
            .all()
        )
        latest_snapshot_id = connection.execute(
            select(job_snapshots.c.id)
            .where(job_snapshots.c.application_id == revision.application_id)
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
        ).scalar_one()
        return RenderOperationSources(
            revision,
            manifest,
            _snapshot_record(snapshot_row),
            _analysis_record(analysis_row),
            _selection_plan_record(plan_row),
            _decision_for_revision(connection, revision_id),
            latest_snapshot_id,
            tuple(_analysis_record(row) for row in analysis_rows),
        )

    def matching_render_artifact(
        self,
        tx: ReadTransaction,
        revision_id: str,
        artifact_type: str,
        content_hash: str,
        lifecycle_status: str,
    ) -> dict | None:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(*artifact_versions.c, artifacts.c.artifact_type)
                .select_from(artifact_versions.join(artifacts))
                .where(
                    artifact_versions.c.revision_id == revision_id,
                    artifacts.c.artifact_type == artifact_type,
                    artifact_versions.c.content_hash == content_hash,
                    artifact_versions.c.lifecycle_status == lifecycle_status,
                )
                .order_by(
                    artifact_versions.c.created_at,
                    artifact_versions.c.version_number,
                )
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else dict(row)
