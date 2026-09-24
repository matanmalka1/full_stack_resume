from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection

from ...application.errors import VALIDATION_STALE, LineageBroken, PreconditionFailed, UnknownRecord
from ...domain.contracts.records import DecisionRecord, ValidationRunLineage
from ...domain.contracts.validation import ValidationReport
from ...util import new_id, utc_now
from .base import json_text_record
from .tables import (
    approved_revisions,
    artifact_versions,
    artifacts,
    decision_records,
    job_analyses,
    job_snapshots,
    validation_runs,
    working_drafts,
)


def _require_owned_snapshot(
    connection: Connection, application_id: str, snapshot_id: str, subject: str
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


def _artifact_version(connection: Connection, artifact_version_id: str) -> dict[str, Any]:
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
    return json_text_record(row, "metadata_json")


def _artifact_version_for_revision(
    connection: Connection,
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
    row = connection.execute(statement).mappings().one_or_none()
    if row is None:
        raise UnknownRecord(f"no {artifact_type} artifact for approved revision {revision_id}")
    return json_text_record(row, "metadata_json")


def _artifact_versions(connection: Connection, application_id: str) -> list[dict[str, Any]]:
    rows = (
        connection.execute(
            select(*artifact_versions.c, artifacts.c.artifact_type, artifacts.c.logical_name)
            .select_from(artifact_versions.join(artifacts))
            .where(artifacts.c.application_id == application_id)
            .order_by(artifact_versions.c.created_at, artifact_versions.c.version_number)
        )
        .mappings()
        .all()
    )
    return [json_text_record(row, "metadata_json") for row in rows]


def _decision_for_artifact_version(
    connection: Connection, artifact_version_id: str
) -> dict[str, Any]:
    row = (
        connection.execute(
            select(
                *decision_records.c,
                approved_revisions.c.application_id,
                approved_revisions.c.job_snapshot_id,
                approved_revisions.c.job_analysis_id,
            )
            .select_from(
                decision_records.join(
                    approved_revisions,
                    approved_revisions.c.id == decision_records.c.approved_revision_id,
                ).join(
                    artifact_versions,
                    artifact_versions.c.revision_id == approved_revisions.c.id,
                )
            )
            .where(artifact_versions.c.id == artifact_version_id)
            .order_by(decision_records.c.created_at.desc())
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise UnknownRecord(f"no decision record for artifact version {artifact_version_id}")
    return json_text_record(row, "structured_json")


def _decision_for_revision(connection: Connection, revision_id: str) -> dict[str, Any]:
    row = (
        connection.execute(
            select(
                *decision_records.c,
                approved_revisions.c.application_id,
                approved_revisions.c.job_snapshot_id,
                approved_revisions.c.job_analysis_id,
            )
            .select_from(
                decision_records.join(
                    approved_revisions,
                    approved_revisions.c.id == decision_records.c.approved_revision_id,
                )
            )
            .where(decision_records.c.approved_revision_id == revision_id)
            .order_by(decision_records.c.created_at.desc())
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise UnknownRecord(f"no decision record for approved revision {revision_id}")
    return json_text_record(row, "structured_json")


def _insert_decision(connection: Connection, record: DecisionRecord) -> None:
    connection.execute(
        insert(decision_records).values(
            id=record.id,
            approved_revision_id=record.approved_revision_id,
            structured_json=record.structured,
            summary=record.summary,
            created_at=record.created_at,
        )
    )


def _latest_artifact_version(
    connection: Connection,
    application_id: str,
    artifact_type: str,
    lifecycle_status: str | None = None,
) -> dict[str, Any]:
    statement = (
        select(*artifact_versions.c, artifacts.c.artifact_type, artifacts.c.logical_name)
        .select_from(artifact_versions.join(artifacts))
        .where(
            artifacts.c.application_id == application_id, artifacts.c.artifact_type == artifact_type
        )
    )
    if lifecycle_status:
        statement = statement.where(artifact_versions.c.lifecycle_status == lifecycle_status)
    statement = statement.order_by(
        artifact_versions.c.created_at.desc(), artifact_versions.c.version_number.desc()
    ).limit(1)
    row = connection.execute(statement).mappings().one_or_none()
    if row is None:
        raise UnknownRecord(f"no {artifact_type} artifact for application {application_id}")
    return json_text_record(row, "metadata_json")


def _latest_decision(connection: Connection, application_id: str) -> dict[str, Any]:
    row = (
        connection.execute(
            select(
                *decision_records.c,
                approved_revisions.c.application_id,
                approved_revisions.c.job_snapshot_id,
                approved_revisions.c.job_analysis_id,
            )
            .select_from(
                decision_records.join(
                    approved_revisions,
                    approved_revisions.c.id == decision_records.c.approved_revision_id,
                )
            )
            .where(approved_revisions.c.application_id == application_id)
            .order_by(
                approved_revisions.c.version_number.desc(),
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
    return json_text_record(row, "structured_json")


def _latest_validation_for_working_draft(
    connection: Connection, working_draft_id: str
) -> dict[str, Any] | None:
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


def _record_validation(
    connection: Connection,
    application_id: str,
    phase: str,
    report: ValidationReport,
    artifact_version_id: str | None = None,
    *,
    lineage: ValidationRunLineage | None = None,
) -> str:
    validation_id = new_id()
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
            or (draft["selection_plan_id"] != lineage.selection_plan_id)
            or (draft["edit_version"] != lineage.edit_version)
            or (draft["content_hash"] != lineage.content_hash)
            or (draft["job_snapshot_id"] != lineage.job_snapshot_id)
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


def _register_artifact_version(
    connection: Connection,
    application_id: str,
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
    artifact_version_id: str | None = None,
) -> str:
    version_id = artifact_version_id or new_id()
    now = utc_now()
    if job_snapshot_id is not None:
        _require_owned_snapshot(connection, application_id, job_snapshot_id, "artifact version")
    if revision_id is not None:
        revision = (
            connection.execute(
                select(
                    approved_revisions.c.application_id, approved_revisions.c.job_snapshot_id
                ).where(approved_revisions.c.id == revision_id)
            )
            .mappings()
            .one_or_none()
        )
        if revision is None or revision["application_id"] != application_id:
            raise LineageBroken(
                "an artifact version cannot reference an approved revision belonging to another application"
            )
        if job_snapshot_id is not None and revision["job_snapshot_id"] != job_snapshot_id:
            raise LineageBroken("an artifact version's revision and job snapshot must match")
    artifact = (
        connection.execute(
            select(artifacts.c.id).where(
                artifacts.c.application_id == application_id,
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


def _validation_for_artifact(
    connection: Connection, application_id: str, phase: str, artifact_version_id: str
) -> ValidationReport:
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


def _validation_lineage(connection: Connection, validation_id: str) -> ValidationRunLineage:
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


def _validation_report(connection: Connection, validation_id: str) -> ValidationReport:
    row = (
        connection.execute(
            select(validation_runs.c.report_json).where(validation_runs.c.id == validation_id)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise UnknownRecord(f"no validation report {validation_id}")
    return ValidationReport.model_validate(row["report_json"])


def _validation_run(connection: Connection, validation_id: str) -> dict[str, Any]:
    """Read immutable validation evidence by ID, irrespective of current draft state."""
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
            ).where(validation_runs.c.id == validation_id, validation_runs.c.phase == "pre-render")
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise UnknownRecord(f"no validation run {validation_id}")
    record = dict(row)
    record["report"] = ValidationReport.model_validate(record.pop("report_json"))
    return record
