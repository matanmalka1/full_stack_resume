from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...domain.models import (
    ApplicationStatus,
    JobAnalysis,
    SelectionManifest,
    SelectionPlan,
)
from ...util import canonical_json, utc_now
from .applications import SqliteApplicationRepository
from .base import SqliteRepositoryBase
from .connection import SqliteUnitOfWork
from .primitives import new_id


_SNAPSHOT_COLUMNS = (
    "id, application_id, version_number, payload_path, source_hash, normalized_hash, "
    "source_url, captured_at, source_metadata_json, content_hash, prior_snapshot_id"
)


def _require_owned_snapshot(
    connection: Any,
    application_id: str | None,
    snapshot_id: str,
    subject: str,
) -> None:
    """Refuse to link a record to a job snapshot another application owns."""
    row = connection.execute(
        "SELECT application_id FROM job_snapshots WHERE id=?", (snapshot_id,)
    ).fetchone()
    if row is None:
        raise ValueError(
            f"a {subject} cannot reference an unknown job snapshot: {snapshot_id}"
        )
    if row["application_id"] != application_id:
        raise ValueError(
            f"a {subject} cannot reference a job snapshot belonging to another application"
        )


class SqlitePreparationRepository(SqliteRepositoryBase):
    def __init__(
        self,
        path: Path,
        connection: Any | None = None,
        applications: SqliteApplicationRepository | None = None,
    ):
        super().__init__(path, connection)
        self.applications = applications or SqliteApplicationRepository(path, connection)

    def bind(self, uow: SqliteUnitOfWork) -> "SqlitePreparationRepository":
        if uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if uow.path.resolve() != self.path.resolve():
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(
            self.path,
            uow.connection,
            self.applications.bind(uow),
        )

    def create_application(
        self,
        *,
        company: str,
        target_role: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None = None,
        source: str = "manual",
        notes: str = "",
        application_id: str | None = None,
        snapshot_id: str | None = None,
        captured_at: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        if not company.strip() or not target_role.strip():
            raise ValueError("company and target role are required")
        if not payload_path or not source_hash or not normalized_hash:
            raise ValueError("snapshot payload path and hashes are required")
        app_id = application_id or new_id()
        snap_id = snapshot_id or new_id()
        now = captured_at or utc_now()

        if self._bound_connection is None:
            with SqliteUnitOfWork(self.path) as uow:
                bound = self.bind(uow)
                bound._create_application_records(
                    app_id,
                    snap_id,
                    company,
                    target_role,
                    payload_path,
                    source_hash,
                    normalized_hash,
                    source_url,
                    source,
                    notes,
                    now,
                    source_metadata,
                )
                uow.commit()
        else:
            self._create_application_records(
                app_id,
                snap_id,
                company,
                target_role,
                payload_path,
                source_hash,
                normalized_hash,
                source_url,
                source,
                notes,
                now,
                source_metadata,
            )
        return app_id, snap_id

    def _create_application_records(
        self,
        app_id: str,
        snap_id: str,
        company: str,
        target_role: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        source: str,
        notes: str,
        now: str,
        source_metadata: dict[str, Any] | None,
    ) -> None:
        self.applications._insert_application(
            application_id=app_id,
            company=company,
            target_role=target_role,
            source_url=source_url,
            notes=notes,
            source=source,
            created_at=now,
        )
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO job_snapshots(id, application_id, version_number, payload_path, source_hash, normalized_hash, source_url, captured_at, source_metadata_json, content_hash, prior_snapshot_id) "
                "VALUES(?, ?, 1, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    snap_id,
                    app_id,
                    payload_path,
                    source_hash,
                    normalized_hash,
                    source_url,
                    now,
                    canonical_json(source_metadata or {}),
                    source_hash,
                ),
            )

    def add_job_snapshot(
        self,
        application_id: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        with self.transaction() as connection:
            prior = connection.execute(
                "SELECT id, version_number FROM job_snapshots WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
            if prior is None:
                raise KeyError(application_id)
            resolved_snapshot_id = snapshot_id or new_id()
            connection.execute(
                "INSERT INTO job_snapshots(id, application_id, version_number, payload_path, source_hash, normalized_hash, source_url, captured_at, source_metadata_json, content_hash, prior_snapshot_id) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    resolved_snapshot_id,
                    application_id,
                    prior["version_number"] + 1,
                    payload_path,
                    source_hash,
                    normalized_hash,
                    source_url,
                    utc_now(),
                    canonical_json(source_metadata or {}),
                    source_hash,
                    prior["id"],
                ),
            )
        return resolved_snapshot_id

    def latest_snapshot(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_SNAPSHOT_COLUMNS} FROM job_snapshots WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no snapshot for application {application_id}")
        return dict(row)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_SNAPSHOT_COLUMNS} FROM job_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no job snapshot {snapshot_id}")
        return dict(row)

    def save_analysis(
        self,
        application_id: str,
        snapshot_id: str,
        analysis: JobAnalysis,
        plan: SelectionManifest,
        *,
        provider: str = "deterministic",
        model: str = "rules-v1",
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
    ) -> tuple[str, SelectionPlan]:
        analysis_id = new_id()
        selection_plan_id = new_id()
        now = utc_now()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS version "
                "FROM job_analyses WHERE application_id=?",
                (application_id,),
            ).fetchone()
            connection.execute(
                "INSERT INTO job_analyses(id, application_id, job_snapshot_id, version_number, structured_json, provider, model, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    analysis_id,
                    application_id,
                    snapshot_id,
                    row["version"],
                    analysis.model_dump_json(),
                    provider,
                    model,
                    now,
                ),
            )
            self._insert_selection_plan(
                connection,
                selection_plan_id,
                application_id,
                analysis_id,
                plan,
                candidate_context_version,
                candidate_context_hash,
                profile_version,
                selection_policy_version,
                track_emphasis_dependencies,
                now,
            )
            connection.execute(
                "UPDATE applications SET language=?, track=?, profile=?, emphasis=?, "
                "classification_confidence=?, fit_level=?, updated_at=? WHERE id=?",
                (
                    analysis.language,
                    analysis.track.value,
                    analysis.profile.value,
                    analysis.emphasis.value,
                    analysis.confidence,
                    analysis.fit.value,
                    now,
                    application_id,
                ),
            )
            current_row = connection.execute(
                "SELECT current_status FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            if current_row is None:
                raise KeyError(application_id)
            current = ApplicationStatus(current_row["current_status"])
            if current in (ApplicationStatus.SAVED, ApplicationStatus.READY):
                reason = (
                    "analysis created"
                    if current is ApplicationStatus.SAVED
                    else "new analysis invalidated the prior ready version"
                )
                self.applications._transition_status(
                    connection,
                    application_id,
                    ApplicationStatus.PREPARING,
                    reason,
                    now,
                )
            plan_row = connection.execute(
                "SELECT * FROM selection_plans WHERE id=?", (selection_plan_id,)
            ).fetchone()
        return analysis_id, self._selection_plan_record(plan_row)

    def create_selection_plan(
        self,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan:
        selection_plan_id = plan_id or new_id()
        now = created_at or utc_now()
        with self.transaction() as connection:
            self._insert_selection_plan(
                connection,
                selection_plan_id,
                application_id,
                job_analysis_id,
                plan,
                candidate_context_version,
                candidate_context_hash,
                profile_version,
                selection_policy_version,
                track_emphasis_dependencies,
                now,
            )
            row = connection.execute(
                "SELECT * FROM selection_plans WHERE id=?", (selection_plan_id,)
            ).fetchone()
        return self._selection_plan_record(row)

    @staticmethod
    def _insert_selection_plan(
        connection: Any,
        selection_plan_id: str,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        created_at: str,
    ) -> None:
        analysis = connection.execute(
            "SELECT application_id FROM job_analyses WHERE id=?", (job_analysis_id,)
        ).fetchone()
        if analysis is None or analysis["application_id"] != application_id:
            raise ValueError(
                "a selection plan cannot reference a job analysis belonging to "
                "another application"
            )
        version = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS version "
            "FROM selection_plans WHERE application_id=?",
            (application_id,),
        ).fetchone()["version"]
        connection.execute(
            "INSERT INTO selection_plans(id, application_id, job_analysis_id, "
            "version_number, plan_json, candidate_context_version, "
            "candidate_context_hash, profile_version, selection_policy_version, "
            "track_emphasis_dependencies_json, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                selection_plan_id,
                application_id,
                job_analysis_id,
                version,
                canonical_json(plan.model_dump(mode="json")),
                candidate_context_version,
                candidate_context_hash,
                profile_version,
                selection_policy_version,
                canonical_json(track_emphasis_dependencies),
                created_at,
            ),
        )

    @staticmethod
    def _selection_plan_record(row: Any) -> SelectionPlan:
        if row is None:
            raise KeyError("selection plan does not exist")
        record = dict(row)
        return SelectionPlan(
            id=record["id"],
            application_id=record["application_id"],
            job_analysis_id=record["job_analysis_id"],
            version_number=record["version_number"],
            plan=SelectionManifest.model_validate_json(record["plan_json"]),
            candidate_context_version=record["candidate_context_version"],
            candidate_context_hash=record["candidate_context_hash"],
            profile_version=record["profile_version"],
            selection_policy_version=record["selection_policy_version"],
            track_emphasis_dependencies=json.loads(
                record["track_emphasis_dependencies_json"]
            ),
            created_at=record["created_at"],
        )

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM selection_plans WHERE id=?", (selection_plan_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"no selection plan {selection_plan_id}")
        return self._selection_plan_record(row)

    def latest_selection_plan(self, application_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM selection_plans WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no selection plan for application {application_id}")
        return self._selection_plan_record(row)

    @staticmethod
    def _analysis_record(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["analysis"] = JobAnalysis.model_validate_json(
            record.pop("structured_json")
        )
        return record

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM job_analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"no job analysis {analysis_id}")
        return self._analysis_record(row)

    def analyses(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM job_analyses WHERE application_id=? "
                "ORDER BY version_number",
                (application_id,),
            ).fetchall()
        return [self._analysis_record(row) for row in rows]

    def latest_analysis(self, application_id: str) -> tuple[str, JobAnalysis]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT id, structured_json FROM job_analyses WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no analysis for application {application_id}")
        return row["id"], JobAnalysis.model_validate_json(row["structured_json"])
