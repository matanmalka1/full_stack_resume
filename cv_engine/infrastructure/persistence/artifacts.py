from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, func, insert, select
from sqlalchemy.engine import Connection

from ...application.errors import (
    VALIDATION_STALE,
    LineageBroken,
    PreconditionFailed,
    UnknownRecord,
)
from ...domain.models import DecisionRecord, ValidationReport, ValidationRunLineage
from ...util import canonical_json, new_id, utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import (
    approved_revisions,
    artifact_versions,
    artifacts,
    decision_records,
    generation_runs,
    job_analyses,
    job_snapshots,
    validation_runs,
    working_drafts,
)


def _json_text_record(row: Any, *fields: str) -> dict[str, Any]:
    record = dict(row)
    for field in fields:
        value = record[field]
        record[field] = None if value is None else canonical_json(value)
    return record


def _require_owned_snapshot(
    connection: Connection,
    application_id: str | None,
    snapshot_id: str,
    subject: str,
) -> None:
    """Refuse to link a record to a job snapshot another application owns."""
    row = (
        connection.execute(
            select(job_snapshots.c.application_id).where(job_snapshots.c.id == snapshot_id)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise LineageBroken(f"a {subject} cannot reference an unknown job snapshot: {snapshot_id}")
    if row["application_id"] != application_id:
        raise LineageBroken(
            f"a {subject} cannot reference a job snapshot belonging to another application"
        )


class SqlAlchemyArtifactRepository(SqlAlchemyRepositoryBase):
    def artifact_inventory(self) -> list[dict[str, Any]]:
        """Every recorded artifact version's path and hash, for reconciliation."""
        with self.read_connection() as connection:
            rows = connection.execute(
                select(artifact_versions.c.path, artifact_versions.c.content_hash)
            ).mappings()
            return [dict(row) for row in rows]

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
        version_id = artifact_version_id or new_id()
        now = utc_now()
        with self.transaction() as connection:
            if job_snapshot_id is not None:
                _require_owned_snapshot(
                    connection, application_id, job_snapshot_id, "artifact version"
                )
            if revision_id is not None:
                revision = (
                    connection.execute(
                        select(
                            approved_revisions.c.application_id,
                            approved_revisions.c.job_snapshot_id,
                        ).where(approved_revisions.c.id == revision_id)
                    )
                    .mappings()
                    .one_or_none()
                )
                if revision is None or revision["application_id"] != application_id:
                    raise LineageBroken(
                        "an artifact version cannot reference an approved revision "
                        "belonging to another application"
                    )
                if job_snapshot_id is not None and revision["job_snapshot_id"] != job_snapshot_id:
                    raise LineageBroken(
                        "an artifact version's revision and job snapshot must match"
                    )
            application_clause = (
                artifacts.c.application_id.is_(None)
                if application_id is None
                else artifacts.c.application_id == application_id
            )
            artifact = (
                connection.execute(
                    select(artifacts.c.id).where(
                        application_clause,
                        artifacts.c.artifact_type == artifact_type,
                        artifacts.c.logical_name == logical_name,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if artifact is None:
                artifact_id = new_id()
                connection.execute(
                    insert(artifacts).values(
                        id=artifact_id,
                        application_id=application_id,
                        artifact_type=artifact_type,
                        logical_name=logical_name,
                        created_at=now,
                    )
                )
            else:
                artifact_id = artifact["id"]
            version = connection.execute(
                select(func.coalesce(func.max(artifact_versions.c.version_number), 0) + 1).where(
                    artifact_versions.c.artifact_id == artifact_id
                )
            ).scalar_one()
            connection.execute(
                insert(artifact_versions).values(
                    id=version_id,
                    artifact_id=artifact_id,
                    version_number=version,
                    lifecycle_status=lifecycle_status,
                    path=path,
                    content_hash=content_hash,
                    created_at=now,
                    approved_at=approved_at,
                    submitted_at=submitted_at,
                    track=track,
                    profile=profile,
                    emphasis=emphasis,
                    facts_version=facts_version,
                    job_snapshot_id=job_snapshot_id,
                    metadata_json=metadata or {},
                    revision_id=revision_id,
                )
            )
        return version_id

    def latest_artifact_version(
        self,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        statement = (
            select(*artifact_versions.c, artifacts.c.artifact_type, artifacts.c.logical_name)
            .select_from(artifact_versions.join(artifacts))
            .where(
                artifacts.c.application_id == application_id,
                artifacts.c.artifact_type == artifact_type,
            )
        )
        if lifecycle_status:
            statement = statement.where(artifact_versions.c.lifecycle_status == lifecycle_status)
        statement = statement.order_by(
            artifact_versions.c.created_at.desc(), artifact_versions.c.version_number.desc()
        ).limit(1)
        with self.read_connection() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no {artifact_type} artifact for application {application_id}")
        return _json_text_record(row, "metadata_json")

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(
                        *artifact_versions.c, artifacts.c.artifact_type, artifacts.c.logical_name
                    )
                    .select_from(artifact_versions.join(artifacts))
                    .where(artifacts.c.application_id == application_id)
                    .order_by(artifact_versions.c.created_at, artifact_versions.c.version_number)
                )
                .mappings()
                .all()
            )
        return [_json_text_record(row, "metadata_json") for row in rows]

    def artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(
                        *artifact_versions.c,
                        artifacts.c.application_id,
                        artifacts.c.artifact_type,
                        artifacts.c.logical_name,
                    )
                    .select_from(artifact_versions.join(artifacts))
                    .where(artifact_versions.c.id == artifact_version_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no artifact version {artifact_version_id}")
        return _json_text_record(row, "metadata_json")

    def artifact_version_for_revision(
        self,
        revision_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        statement = (
            select(
                *artifact_versions.c,
                artifacts.c.application_id,
                artifacts.c.artifact_type,
                artifacts.c.logical_name,
            )
            .select_from(artifact_versions.join(artifacts))
            .where(
                artifact_versions.c.revision_id == revision_id,
                artifacts.c.artifact_type == artifact_type,
            )
        )
        if lifecycle_status is not None:
            statement = statement.where(artifact_versions.c.lifecycle_status == lifecycle_status)
        statement = statement.order_by(
            artifact_versions.c.created_at.desc(), artifact_versions.c.version_number.desc()
        ).limit(1)
        with self.read_connection() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no {artifact_type} artifact for approved revision {revision_id}")
        return _json_text_record(row, "metadata_json")

    def insert_decision(self, record: DecisionRecord) -> None:
        with self.transaction() as connection:
            connection.execute(
                insert(decision_records).values(
                    id=record.id,
                    application_id=record.application_id,
                    artifact_version_id=record.artifact_version_id,
                    job_snapshot_id=record.job_snapshot_id,
                    job_analysis_id=record.job_analysis_id,
                    structured_json=record.structured,
                    summary=record.summary,
                    created_at=record.created_at,
                )
            )

    def latest_decision(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(decision_records)
                    .select_from(
                        decision_records.join(
                            artifact_versions,
                            artifact_versions.c.id == decision_records.c.artifact_version_id,
                        )
                    )
                    .where(decision_records.c.application_id == application_id)
                    .order_by(
                        artifact_versions.c.version_number.desc(),
                        decision_records.c.created_at.desc(),
                        decision_records.c.id,
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no decision record for application {application_id}")
        return _json_text_record(row, "structured_json")

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(decision_records)
                    .where(decision_records.c.artifact_version_id == artifact_version_id)
                    .order_by(decision_records.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no decision record for artifact version {artifact_version_id}")
        return _json_text_record(row, "structured_json")

    def decision_for_revision(self, revision_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(decision_records)
                    .select_from(
                        decision_records.join(
                            artifact_versions,
                            artifact_versions.c.id == decision_records.c.artifact_version_id,
                        )
                    )
                    .where(artifact_versions.c.revision_id == revision_id)
                    .order_by(decision_records.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no decision record for approved revision {revision_id}")
        return _json_text_record(row, "structured_json")

    def record_generation_run(self, values: dict[str, Any]) -> str:
        run_id = values.get("id") or new_id()
        with self.transaction() as connection:
            connection.execute(
                insert(generation_runs).values(
                    id=run_id,
                    application_id=values["application_id"],
                    created_at=values.get("created_at", utc_now()),
                    engine_version=values["engine_version"],
                    profile_version=values["profile_version"],
                    rendering_rules_version=values["rendering_rules_version"],
                    facts_version=values["facts_version"],
                    ai_provider=values["ai_provider"],
                    ai_model=values["ai_model"],
                    task_contract_version=values["task_contract_version"],
                    prompt_version=values["prompt_version"],
                    job_analysis_version=values["job_analysis_version"],
                    instruction_overrides_json=values.get("instruction_overrides", {}),
                    status=values.get("status", "completed"),
                )
            )
        return run_id

    def record_validation(
        self,
        application_id: str,
        phase: str,
        report: ValidationReport,
        artifact_version_id: str | None = None,
        *,
        lineage: ValidationRunLineage | None = None,
    ) -> str:
        validation_id = new_id()
        with self.transaction() as connection:
            if lineage is not None:
                draft = (
                    connection.execute(
                        select(
                            working_drafts.c.application_id,
                            working_drafts.c.job_analysis_id,
                            working_drafts.c.selection_plan_id,
                            working_drafts.c.edit_version,
                            working_drafts.c.content_hash,
                            job_analyses.c.job_snapshot_id,
                        )
                        .select_from(working_drafts.join(job_analyses))
                        .where(working_drafts.c.id == lineage.working_draft_id)
                    )
                    .mappings()
                    .one_or_none()
                )
                if (
                    draft is None
                    or draft["application_id"] != application_id
                    or draft["job_analysis_id"] != lineage.job_analysis_id
                    or draft["selection_plan_id"] != lineage.selection_plan_id
                    or draft["edit_version"] != lineage.edit_version
                    or draft["content_hash"] != lineage.content_hash
                    or draft["job_snapshot_id"] != lineage.job_snapshot_id
                ):
                    raise PreconditionFailed(
                        "validation lineage does not match the exact working draft context",
                        code=VALIDATION_STALE,
                    )
            connection.execute(
                insert(validation_runs).values(
                    id=validation_id,
                    application_id=application_id,
                    artifact_version_id=artifact_version_id,
                    phase=phase,
                    report_json=report.model_dump(mode="json"),
                    created_at=utc_now(),
                    working_draft_id=lineage.working_draft_id if lineage else None,
                    edit_version=lineage.edit_version if lineage else None,
                    content_hash=lineage.content_hash if lineage else None,
                    job_snapshot_id=lineage.job_snapshot_id if lineage else None,
                    job_analysis_id=lineage.job_analysis_id if lineage else None,
                    selection_plan_id=lineage.selection_plan_id if lineage else None,
                    knowledge_context_hash=lineage.knowledge_context_hash if lineage else None,
                    validator_versions_json=lineage.validator_versions if lineage else None,
                )
            )
        return validation_id

    def validation_lineage(self, validation_id: str) -> ValidationRunLineage:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(
                        validation_runs.c.working_draft_id,
                        validation_runs.c.edit_version,
                        validation_runs.c.content_hash,
                        validation_runs.c.job_snapshot_id,
                        validation_runs.c.job_analysis_id,
                        validation_runs.c.selection_plan_id,
                        validation_runs.c.knowledge_context_hash,
                        validation_runs.c.validator_versions_json,
                    ).where(validation_runs.c.id == validation_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None or row["working_draft_id"] is None:
            raise UnknownRecord(f"no validation lineage {validation_id}")
        return ValidationRunLineage(
            working_draft_id=row["working_draft_id"],
            edit_version=row["edit_version"],
            content_hash=row["content_hash"],
            job_snapshot_id=row["job_snapshot_id"],
            job_analysis_id=row["job_analysis_id"],
            selection_plan_id=row["selection_plan_id"],
            knowledge_context_hash=row["knowledge_context_hash"],
            validator_versions=row["validator_versions_json"],
        )

    def latest_validation_for_working_draft(self, working_draft_id: str) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(
                        validation_runs.c.id,
                        validation_runs.c.edit_version,
                        validation_runs.c.content_hash,
                        validation_runs.c.job_snapshot_id,
                        validation_runs.c.job_analysis_id,
                        validation_runs.c.selection_plan_id,
                        validation_runs.c.report_json,
                        validation_runs.c.created_at,
                    )
                    .where(validation_runs.c.working_draft_id == working_draft_id)
                    .order_by(validation_runs.c.created_at.desc(), validation_runs.c.seq.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        record = dict(row)
        record["report"] = ValidationReport.model_validate(record.pop("report_json"))
        return record

    def validation_for_artifact(
        self,
        application_id: str,
        phase: str,
        artifact_version_id: str,
    ) -> ValidationReport:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(validation_runs.c.report_json)
                    .where(
                        validation_runs.c.application_id == application_id,
                        validation_runs.c.phase == phase,
                        validation_runs.c.artifact_version_id == artifact_version_id,
                    )
                    .order_by(validation_runs.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(
                f"no {phase} validation references artifact version {artifact_version_id}"
            )
        return ValidationReport.model_validate(row["report_json"])

    def validation_report(self, validation_id: str) -> ValidationReport:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(validation_runs.c.report_json).where(
                        validation_runs.c.id == validation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no validation report {validation_id}")
        return ValidationReport.model_validate(row["report_json"])

    def validation_run(self, validation_id: str) -> dict[str, Any]:
        """Read immutable validation evidence by ID, irrespective of current draft state."""
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(
                        validation_runs.c.id,
                        validation_runs.c.application_id,
                        validation_runs.c.working_draft_id,
                        validation_runs.c.edit_version,
                        validation_runs.c.content_hash,
                        validation_runs.c.report_json,
                        validation_runs.c.created_at,
                    ).where(
                        validation_runs.c.id == validation_id,
                        validation_runs.c.phase == "pre-render",
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no validation run {validation_id}")
        record = dict(row)
        record["report"] = ValidationReport.model_validate(record.pop("report_json"))
        return record

    def integrity_check(self) -> list[str]:
        catalog = MetaData()
        pg_constraint = Table(
            "pg_constraint",
            catalog,
            Column("conname", String),
            Column("connamespace", Integer),
            Column("contype", String),
            Column("convalidated", Boolean),
            schema="pg_catalog",
        )
        pg_namespace = Table(
            "pg_namespace",
            catalog,
            Column("oid", Integer),
            Column("nspname", String),
            schema="pg_catalog",
        )
        with self.read_connection() as connection:
            names = connection.execute(
                select(pg_constraint.c.conname)
                .select_from(
                    pg_constraint.join(
                        pg_namespace,
                        pg_namespace.c.oid == pg_constraint.c.connamespace,
                    )
                )
                .where(
                    pg_constraint.c.contype == "f",
                    pg_constraint.c.convalidated.is_(False),
                    pg_namespace.c.nspname == func.current_schema(),
                )
                .order_by(pg_constraint.c.conname)
            ).scalars()
            return [f"foreign key constraint not validated: {name}" for name in names]
