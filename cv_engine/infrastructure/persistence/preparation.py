from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self

from ...application.errors import (
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ...application.ports import UnitOfWork
from ...domain.models import (
    JobAnalysis,
    SelectionManifest,
    SelectionPlan,
)
from ...util import canonical_json, new_id, utc_now
from .applications import SqliteApplicationRepository
from .base import SqliteRepositoryBase, sqlite_unit_of_work
from .connection import SqliteUnitOfWork

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
        raise LineageBroken(f"a {subject} cannot reference an unknown job snapshot: {snapshot_id}")
    if row["application_id"] != application_id:
        raise LineageBroken(
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

    def bind(self, uow: UnitOfWork) -> Self:
        sqlite_uow = sqlite_unit_of_work(uow)
        if sqlite_uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if sqlite_uow.path.resolve() != self.path.resolve():
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(
            self.path,
            sqlite_uow.connection,
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
        actor_type: str = "user",
        client: str = "cli",
        installation_id: str = "unconfigured-test-installation",
    ) -> tuple[str, str]:
        if not company.strip() or not target_role.strip():
            raise PreconditionFailed("company and target role are required")
        if not payload_path or not source_hash or not normalized_hash:
            raise PreconditionFailed("snapshot payload path and hashes are required")
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
                    actor_type,
                    client,
                    installation_id,
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
                actor_type,
                client,
                installation_id,
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
        actor_type: str,
        client: str,
        installation_id: str,
    ) -> None:
        self.applications._insert_application(
            application_id=app_id,
            company=company,
            target_role=target_role,
            source_url=source_url,
            notes=notes,
            source=source,
            created_at=now,
            actor_type=actor_type,
            client=client,
            installation_id=installation_id,
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
                raise UnknownRecord(application_id)
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

    def duplicate_application_inputs(self) -> list[dict[str, Any]]:
        """Return the stored inputs needed by application duplicate policy.

        The adapter deliberately does not decide what constitutes a duplicate.
        Normalization and the three matching contracts belong to the application
        use-case, not to SQLite collation rules.
        """
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT a.id AS application_id, a.company, a.target_role, "
                "j.source_url, j.normalized_hash "
                "FROM applications AS a JOIN job_snapshots AS j ON j.application_id=a.id "
                "ORDER BY a.created_at, a.id, j.version_number"
            ).fetchall()
        return [dict(row) for row in rows]

    def snapshot_for_content_hash(
        self, application_id: str, content_hash: str
    ) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_SNAPSHOT_COLUMNS} FROM job_snapshots "
                "WHERE application_id=? AND content_hash=?",
                (application_id, content_hash),
            ).fetchone()
        return dict(row) if row is not None else None

    def latest_snapshot(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_SNAPSHOT_COLUMNS} FROM job_snapshots WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise UnknownRecord(f"no snapshot for application {application_id}")
        return dict(row)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_SNAPSHOT_COLUMNS} FROM job_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise UnknownRecord(f"no job snapshot {snapshot_id}")
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
            existing = connection.execute(
                "SELECT * FROM selection_plans WHERE id=?", (selection_plan_id,)
            ).fetchone()
            if existing is not None:
                stored = self._selection_plan_record(existing)
                expected = {
                    "application_id": application_id,
                    "job_analysis_id": job_analysis_id,
                    "plan": plan,
                    "candidate_context_version": candidate_context_version,
                    "candidate_context_hash": candidate_context_hash,
                    "profile_version": profile_version,
                    "selection_policy_version": selection_policy_version,
                    "track_emphasis_dependencies": track_emphasis_dependencies,
                    "created_at": now,
                }
                actual = {key: getattr(stored, key) for key in expected}
                if actual != expected:
                    raise StateConflict("selection plan identity already has different content")
                return stored
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
            raise LineageBroken(
                "a selection plan cannot reference a job analysis belonging to another application"
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
            raise UnknownRecord("selection plan does not exist")
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
            track_emphasis_dependencies=json.loads(record["track_emphasis_dependencies_json"]),
            created_at=record["created_at"],
        )

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM selection_plans WHERE id=?", (selection_plan_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord(f"no selection plan {selection_plan_id}")
        return self._selection_plan_record(row)

    def latest_selection_plan(self, application_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM selection_plans WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise UnknownRecord(f"no selection plan for application {application_id}")
        return self._selection_plan_record(row)

    @staticmethod
    def _analysis_record(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["analysis"] = JobAnalysis.model_validate_json(record.pop("structured_json"))
        return record

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM job_analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return self._analysis_record(row)

    def analyses(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM job_analyses WHERE application_id=? ORDER BY version_number",
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
            raise UnknownRecord(f"no analysis for application {application_id}")
        return row["id"], JobAnalysis.model_validate_json(row["structured_json"])
