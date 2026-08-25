from __future__ import annotations

from typing import Any, Self

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection, Engine

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
from ...util import new_id, utc_now
from .applications import SqlAlchemyApplicationRepository
from .base import SqlAlchemyRepositoryBase, sqlalchemy_unit_of_work
from .connection import SqlAlchemyUnitOfWork
from .tables import applications, job_analyses, job_snapshots, selection_plans


class SqlAlchemyPreparationRepository(SqlAlchemyRepositoryBase):
    def __init__(
        self,
        engine: Engine,
        connection: Connection | None = None,
        applications: SqlAlchemyApplicationRepository | None = None,
    ):
        super().__init__(engine, connection)
        self.applications = applications or SqlAlchemyApplicationRepository(engine, connection)

    def bind(self, uow: UnitOfWork) -> Self:
        sqlalchemy_uow = sqlalchemy_unit_of_work(uow)
        if sqlalchemy_uow.connection is None:
            raise RuntimeError("UnitOfWork is not active")
        if sqlalchemy_uow.engine is not self.engine:
            raise ValueError("UnitOfWork belongs to another database")
        return type(self)(
            self.engine,
            sqlalchemy_uow.connection,
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
            with SqlAlchemyUnitOfWork(self.engine) as uow:
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
                insert(job_snapshots).values(
                    id=snap_id,
                    application_id=app_id,
                    version_number=1,
                    payload_path=payload_path,
                    source_hash=source_hash,
                    normalized_hash=normalized_hash,
                    source_url=source_url,
                    captured_at=now,
                    source_metadata_json=source_metadata or {},
                    content_hash=source_hash,
                    prior_snapshot_id=None,
                )
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
        captured_at: str | None = None,
    ) -> str:
        with self.transaction() as connection:
            prior = connection.execute(
                select(job_snapshots.c.id, job_snapshots.c.version_number)
                .where(job_snapshots.c.application_id == application_id)
                .order_by(job_snapshots.c.version_number.desc())
                .limit(1)
            ).mappings().one_or_none()
            if prior is None:
                raise UnknownRecord(application_id)
            resolved_snapshot_id = snapshot_id or new_id()
            connection.execute(
                insert(job_snapshots).values(
                    id=resolved_snapshot_id,
                    application_id=application_id,
                    version_number=prior["version_number"] + 1,
                    payload_path=payload_path,
                    source_hash=source_hash,
                    normalized_hash=normalized_hash,
                    source_url=source_url,
                    captured_at=captured_at or utc_now(),
                    source_metadata_json=source_metadata or {},
                    content_hash=source_hash,
                    prior_snapshot_id=prior["id"],
                )
            )
        return resolved_snapshot_id

    def duplicate_application_inputs(self) -> list[dict[str, Any]]:
        """Return the stored inputs needed by application duplicate policy.

        The adapter deliberately does not decide what constitutes a duplicate.
        Normalization and the three matching contracts belong to the application
        use-case, not to database collation rules.
        """
        with self.read_connection() as connection:
            rows = connection.execute(
                select(
                    applications.c.id.label("application_id"),
                    applications.c.company,
                    applications.c.target_role,
                    job_snapshots.c.source_url,
                    job_snapshots.c.normalized_hash,
                )
                .select_from(
                    applications.join(
                        job_snapshots,
                        job_snapshots.c.application_id == applications.c.id,
                    )
                )
                .order_by(
                    applications.c.created_at,
                    applications.c.id,
                    job_snapshots.c.version_number,
                )
            ).mappings().all()
        return [dict(row) for row in rows]

    def snapshot_for_content_hash(
        self, application_id: str, content_hash: str
    ) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = connection.execute(
                select(job_snapshots).where(
                    job_snapshots.c.application_id == application_id,
                    job_snapshots.c.content_hash == content_hash,
                )
            ).mappings().one_or_none()
        return dict(row) if row is not None else None

    def latest_snapshot(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                select(job_snapshots)
                .where(job_snapshots.c.application_id == application_id)
                .order_by(job_snapshots.c.version_number.desc())
                .limit(1)
            ).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no snapshot for application {application_id}")
        return dict(row)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                select(job_snapshots).where(job_snapshots.c.id == snapshot_id)
            ).mappings().one_or_none()
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
            version = connection.execute(
                select(
                    (func.coalesce(func.max(job_analyses.c.version_number), 0) + 1).label(
                        "version"
                    )
                ).where(job_analyses.c.application_id == application_id)
            ).scalar_one()
            connection.execute(
                insert(job_analyses).values(
                    id=analysis_id,
                    application_id=application_id,
                    job_snapshot_id=snapshot_id,
                    version_number=version,
                    structured_json=analysis.model_dump(mode="json"),
                    provider=provider,
                    model=model,
                    created_at=now,
                )
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
                update(applications)
                .where(applications.c.id == application_id)
                .values(
                    language=analysis.language,
                    track=analysis.track.value,
                    profile=analysis.profile.value,
                    emphasis=analysis.emphasis.value,
                    classification_confidence=analysis.confidence,
                    fit_level=analysis.fit.value,
                    updated_at=now,
                )
            )
            plan_row = connection.execute(
                select(selection_plans).where(selection_plans.c.id == selection_plan_id)
            ).mappings().one_or_none()
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
                select(selection_plans).where(selection_plans.c.id == selection_plan_id)
            ).mappings().one_or_none()
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
                select(selection_plans).where(selection_plans.c.id == selection_plan_id)
            ).mappings().one_or_none()
        return self._selection_plan_record(row)

    @staticmethod
    def _insert_selection_plan(
        connection: Connection,
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
            select(job_analyses.c.application_id).where(job_analyses.c.id == job_analysis_id)
        ).mappings().one_or_none()
        if analysis is None or analysis["application_id"] != application_id:
            raise LineageBroken(
                "a selection plan cannot reference a job analysis belonging to another application"
            )
        version = connection.execute(
            select(
                (func.coalesce(func.max(selection_plans.c.version_number), 0) + 1).label(
                    "version"
                )
            ).where(selection_plans.c.application_id == application_id)
        ).scalar_one()
        connection.execute(
            insert(selection_plans).values(
                id=selection_plan_id,
                application_id=application_id,
                job_analysis_id=job_analysis_id,
                version_number=version,
                plan_json=plan.model_dump(mode="json"),
                candidate_context_version=candidate_context_version,
                candidate_context_hash=candidate_context_hash,
                profile_version=profile_version,
                selection_policy_version=selection_policy_version,
                track_emphasis_dependencies_json=track_emphasis_dependencies,
                created_at=created_at,
            )
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
            plan=SelectionManifest.model_validate(record["plan_json"]),
            candidate_context_version=record["candidate_context_version"],
            candidate_context_hash=record["candidate_context_hash"],
            profile_version=record["profile_version"],
            selection_policy_version=record["selection_policy_version"],
            track_emphasis_dependencies=record["track_emphasis_dependencies_json"],
            created_at=record["created_at"],
        )

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = connection.execute(
                select(selection_plans).where(selection_plans.c.id == selection_plan_id)
            ).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no selection plan {selection_plan_id}")
        return self._selection_plan_record(row)

    def latest_selection_plan(self, application_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = connection.execute(
                select(selection_plans)
                .where(selection_plans.c.application_id == application_id)
                .order_by(selection_plans.c.version_number.desc())
                .limit(1)
            ).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no selection plan for application {application_id}")
        return self._selection_plan_record(row)

    @staticmethod
    def _analysis_record(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["analysis"] = JobAnalysis.model_validate(record.pop("structured_json"))
        return record

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                select(job_analyses).where(job_analyses.c.id == analysis_id)
            ).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return self._analysis_record(row)

    def analyses(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                select(job_analyses)
                .where(job_analyses.c.application_id == application_id)
                .order_by(job_analyses.c.version_number)
            ).mappings().all()
        return [self._analysis_record(row) for row in rows]

    def latest_analysis(self, application_id: str) -> tuple[str, JobAnalysis]:
        with self.read_connection() as connection:
            row = connection.execute(
                select(job_analyses.c.id, job_analyses.c.structured_json)
                .where(job_analyses.c.application_id == application_id)
                .order_by(job_analyses.c.version_number.desc())
                .limit(1)
            ).mappings().one_or_none()
        if row is None:
            raise UnknownRecord(f"no analysis for application {application_id}")
        return row["id"], JobAnalysis.model_validate(row["structured_json"])
