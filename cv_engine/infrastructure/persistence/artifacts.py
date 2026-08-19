from __future__ import annotations

import json
from typing import Any

from ...domain.models import DecisionRecord, ValidationReport, ValidationRunLineage
from ...util import canonical_json, new_id, utc_now
from .base import SqliteRepositoryBase
from .connection import integrity_results
from .preparation import _require_owned_snapshot


class SqliteArtifactRepository(SqliteRepositoryBase):
    def artifact_inventory(self) -> list[dict[str, Any]]:
        """Every recorded artifact version's path and hash, for reconciliation."""
        with self.read_connection() as connection:
            rows = connection.execute("SELECT path, content_hash FROM artifact_versions").fetchall()
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
                revision = connection.execute(
                    "SELECT application_id, job_snapshot_id FROM approved_revisions WHERE id=?",
                    (revision_id,),
                ).fetchone()
                if revision is None or revision["application_id"] != application_id:
                    raise ValueError(
                        "an artifact version cannot reference an approved revision "
                        "belonging to another application"
                    )
                if job_snapshot_id is not None and revision["job_snapshot_id"] != job_snapshot_id:
                    raise ValueError("an artifact version's revision and job snapshot must match")
            artifact = connection.execute(
                "SELECT id FROM artifacts WHERE application_id IS ? "
                "AND artifact_type=? AND logical_name=?",
                (application_id, artifact_type, logical_name),
            ).fetchone()
            if artifact is None:
                artifact_id = new_id()
                connection.execute(
                    "INSERT INTO artifacts(id, application_id, artifact_type, logical_name, created_at) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (artifact_id, application_id, artifact_type, logical_name, now),
                )
            else:
                artifact_id = artifact["id"]
            version = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS version "
                "FROM artifact_versions WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()["version"]
            connection.execute(
                "INSERT INTO artifact_versions(id, artifact_id, version_number, lifecycle_status, path, content_hash, created_at, approved_at, submitted_at, track, profile, emphasis, facts_version, job_snapshot_id, metadata_json, revision_id) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version_id,
                    artifact_id,
                    version,
                    lifecycle_status,
                    path,
                    content_hash,
                    now,
                    approved_at,
                    submitted_at,
                    track,
                    profile,
                    emphasis,
                    facts_version,
                    job_snapshot_id,
                    canonical_json(metadata or {}),
                    revision_id,
                ),
            )
        return version_id

    def latest_artifact_version(
        self,
        application_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        query = (
            "SELECT av.*, a.artifact_type, a.logical_name FROM artifact_versions av "
            "JOIN artifacts a ON a.id=av.artifact_id "
            "WHERE a.application_id=? AND a.artifact_type=?"
        )
        params: list[Any] = [application_id, artifact_type]
        if lifecycle_status:
            query += " AND av.lifecycle_status=?"
            params.append(lifecycle_status)
        query += " ORDER BY av.created_at DESC, av.version_number DESC LIMIT 1"
        with self.read_connection() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise KeyError(f"no {artifact_type} artifact for application {application_id}")
        return dict(row)

    def artifact_versions(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT av.*, a.artifact_type, a.logical_name FROM artifact_versions av "
                "JOIN artifacts a ON a.id=av.artifact_id WHERE a.application_id=? "
                "ORDER BY av.created_at, av.version_number",
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT av.*, a.application_id, a.artifact_type, a.logical_name "
                "FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
                "WHERE av.id=?",
                (artifact_version_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no artifact version {artifact_version_id}")
        return dict(row)

    def artifact_version_for_revision(
        self,
        revision_id: str,
        artifact_type: str,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        query = (
            "SELECT av.*, a.application_id, a.artifact_type, a.logical_name "
            "FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
            "WHERE av.revision_id=? AND a.artifact_type=?"
        )
        params: list[Any] = [revision_id, artifact_type]
        if lifecycle_status is not None:
            query += " AND av.lifecycle_status=?"
            params.append(lifecycle_status)
        query += " ORDER BY av.created_at DESC, av.version_number DESC LIMIT 1"
        with self.read_connection() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise KeyError(f"no {artifact_type} artifact for approved revision {revision_id}")
        return dict(row)

    def insert_decision(self, record: DecisionRecord) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO decision_records(id, application_id, artifact_version_id, job_snapshot_id, job_analysis_id, structured_json, summary, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.application_id,
                    record.artifact_version_id,
                    record.job_snapshot_id,
                    record.job_analysis_id,
                    canonical_json(record.structured),
                    record.summary,
                    record.created_at,
                ),
            )

    def latest_decision(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM decision_records WHERE application_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no decision record for application {application_id}")
        return dict(row)

    def decision_for_artifact_version(self, artifact_version_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM decision_records WHERE artifact_version_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (artifact_version_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no decision record for artifact version {artifact_version_id}")
        return dict(row)

    def decision_for_revision(self, revision_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT decisions.* FROM decision_records AS decisions "
                "JOIN artifact_versions AS versions "
                "ON versions.id=decisions.artifact_version_id "
                "WHERE versions.revision_id=? ORDER BY decisions.created_at DESC LIMIT 1",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no decision record for approved revision {revision_id}")
        return dict(row)

    def record_generation_run(self, values: dict[str, Any]) -> str:
        run_id = values.get("id") or new_id()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO generation_runs(id, application_id, created_at, engine_version, profile_version, rendering_rules_version, facts_version, ai_provider, ai_model, task_contract_version, prompt_version, job_analysis_version, instruction_overrides_json, status) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    values["application_id"],
                    values.get("created_at", utc_now()),
                    values["engine_version"],
                    values["profile_version"],
                    values["rendering_rules_version"],
                    values["facts_version"],
                    values["ai_provider"],
                    values["ai_model"],
                    values["task_contract_version"],
                    values["prompt_version"],
                    values["job_analysis_version"],
                    canonical_json(values.get("instruction_overrides", {})),
                    values.get("status", "completed"),
                ),
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
                draft = connection.execute(
                    "SELECT wd.application_id, wd.job_analysis_id, "
                    "wd.selection_plan_id, wd.edit_version, wd.content_hash, "
                    "ja.job_snapshot_id FROM working_drafts wd "
                    "JOIN job_analyses ja ON ja.id=wd.job_analysis_id "
                    "WHERE wd.id=?",
                    (lineage.working_draft_id,),
                ).fetchone()
                if (
                    draft is None
                    or draft["application_id"] != application_id
                    or draft["job_analysis_id"] != lineage.job_analysis_id
                    or draft["selection_plan_id"] != lineage.selection_plan_id
                    or draft["edit_version"] != lineage.edit_version
                    or draft["content_hash"] != lineage.content_hash
                    or draft["job_snapshot_id"] != lineage.job_snapshot_id
                ):
                    raise ValueError(
                        "validation lineage does not match the exact working draft context"
                    )
            connection.execute(
                "INSERT INTO validation_runs(id, application_id, artifact_version_id, "
                "phase, report_json, created_at, working_draft_id, edit_version, "
                "content_hash, job_snapshot_id, job_analysis_id, selection_plan_id, "
                "knowledge_context_hash, validator_versions_json) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validation_id,
                    application_id,
                    artifact_version_id,
                    phase,
                    report.model_dump_json(),
                    utc_now(),
                    lineage.working_draft_id if lineage else None,
                    lineage.edit_version if lineage else None,
                    lineage.content_hash if lineage else None,
                    lineage.job_snapshot_id if lineage else None,
                    lineage.job_analysis_id if lineage else None,
                    lineage.selection_plan_id if lineage else None,
                    lineage.knowledge_context_hash if lineage else None,
                    canonical_json(lineage.validator_versions) if lineage else None,
                ),
            )
        return validation_id

    def validation_lineage(self, validation_id: str) -> ValidationRunLineage:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT working_draft_id, edit_version, content_hash, job_snapshot_id, "
                "job_analysis_id, selection_plan_id, knowledge_context_hash, "
                "validator_versions_json FROM validation_runs WHERE id=?",
                (validation_id,),
            ).fetchone()
        if row is None or row["working_draft_id"] is None:
            raise KeyError(f"no validation lineage {validation_id}")
        return ValidationRunLineage(
            working_draft_id=row["working_draft_id"],
            edit_version=row["edit_version"],
            content_hash=row["content_hash"],
            job_snapshot_id=row["job_snapshot_id"],
            job_analysis_id=row["job_analysis_id"],
            selection_plan_id=row["selection_plan_id"],
            knowledge_context_hash=row["knowledge_context_hash"],
            validator_versions=json.loads(row["validator_versions_json"]),
        )

    def latest_validation(self, application_id: str, phase: str | None = None) -> ValidationReport:
        query = "SELECT report_json FROM validation_runs WHERE application_id=?"
        params: list[Any] = [application_id]
        if phase:
            query += " AND phase=?"
            params.append(phase)
        query += " ORDER BY created_at DESC LIMIT 1"
        with self.read_connection() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise KeyError(f"no validation report for application {application_id}")
        return ValidationReport.model_validate_json(row["report_json"])

    def latest_validation_for_working_draft(
        self, working_draft_id: str
    ) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT id, edit_version, content_hash, job_snapshot_id, job_analysis_id, "
                "selection_plan_id, report_json, created_at FROM validation_runs "
                "WHERE working_draft_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (working_draft_id,),
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["report"] = ValidationReport.model_validate_json(record.pop("report_json"))
        return record

    def validation_for_artifact(
        self,
        application_id: str,
        phase: str,
        artifact_version_id: str,
    ) -> ValidationReport:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT report_json FROM validation_runs WHERE application_id=? "
                "AND phase=? AND artifact_version_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (application_id, phase, artifact_version_id),
            ).fetchone()
        if row is None:
            raise KeyError(
                f"no {phase} validation references artifact version {artifact_version_id}"
            )
        return ValidationReport.model_validate_json(row["report_json"])

    def validation_report(self, validation_id: str) -> ValidationReport:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT report_json FROM validation_runs WHERE id=?", (validation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"no validation report {validation_id}")
        return ValidationReport.model_validate_json(row["report_json"])

    def integrity_check(self) -> list[str]:
        problems: list[str] = []
        with self.read_connection() as connection:
            result, fk_rows = integrity_results(connection)
            if result != "ok":
                problems.append(f"SQLite integrity_check: {result}")
            problems.extend(f"foreign key violation: {tuple(row)}" for row in fk_rows)
        return problems
