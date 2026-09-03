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
    AcceptedGap,
    JobAnalysis,
    SelectionManifest,
    SelectionPlan,
    merge_accepted_gaps,
)
from ...util import canonical_json, new_id, utc_now
from .applications import SqlAlchemyApplicationRepository
from .base import SqlAlchemyRepositoryBase, sqlalchemy_unit_of_work
from .connection import SqlAlchemyUnitOfWork
from .tables import applications, job_analyses, job_snapshots, selection_plans


def _snapshot_record(row: Any) -> dict[str, Any]:
    record = dict(row)
    record["source_metadata_json"] = canonical_json(record["source_metadata_json"])
    return record


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
        client: str,
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
            prior = (
                connection.execute(
                    select(job_snapshots.c.id, job_snapshots.c.version_number)
                    .where(job_snapshots.c.application_id == application_id)
                    .order_by(job_snapshots.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
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
            rows = (
                connection.execute(
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
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    def snapshot_for_content_hash(
        self, application_id: str, content_hash: str
    ) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(job_snapshots).where(
                        job_snapshots.c.application_id == application_id,
                        job_snapshots.c.content_hash == content_hash,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return _snapshot_record(row) if row is not None else None

    def latest_snapshot(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(job_snapshots)
                    .where(job_snapshots.c.application_id == application_id)
                    .order_by(job_snapshots.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no snapshot for application {application_id}")
        return _snapshot_record(row)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(select(job_snapshots).where(job_snapshots.c.id == snapshot_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no job snapshot {snapshot_id}")
        return _snapshot_record(row)

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
        accepted_requirement_ids: list[str] | None = None,
        acceptance_actor: str = "",
        acceptance_reason: str | None = None,
        expected_selection_plan_id: str | None = None,
    ) -> tuple[str, SelectionPlan]:
        """Write one analysis and its initial plan as a single record.

        The requirement ids are ids and not records: the acceptance names the
        analysis it was made against, and that analysis is allocated here. The
        caller has already refused any id that does not name a hard gap of the
        analysis being written, so what arrives is a decision about gaps this
        analysis actually states.
        """
        analysis_id = new_id()
        selection_plan_id = new_id()
        now = utc_now()
        with self.transaction() as connection:
            self._lock_application(connection, application_id)
            # Allocated under the lock. Read before it, the highest version is
            # whatever the snapshot happened to see, and the insert collides on
            # the unique constraint instead of taking the next number.
            version = connection.execute(
                select(
                    (func.coalesce(func.max(job_analyses.c.version_number), 0) + 1).label("version")
                ).where(job_analyses.c.application_id == application_id)
            ).scalar_one()
            self._active_plan(connection, application_id, expected_selection_plan_id)
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
                # A new analysis inherits nothing: the carry is keyed on the
                # analysis id, and this one did not exist a moment ago. What it
                # may carry is an acceptance submitted with the decision that
                # created it, stamped with the analysis allocated above so it
                # can never read as a decision about a different one.
                accepted_gaps=[
                    AcceptedGap(
                        requirement_id=requirement_id,
                        job_analysis_id=analysis_id,
                        actor=acceptance_actor,
                        accepted_at=now,
                        reason=acceptance_reason,
                    )
                    for requirement_id in accepted_requirement_ids or []
                ],
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
            plan_row = (
                connection.execute(
                    select(selection_plans).where(selection_plans.c.id == selection_plan_id)
                )
                .mappings()
                .one_or_none()
            )
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
        new_acceptances: list[AcceptedGap] | None = None,
        expected_selection_plan_id: str | None = None,
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan:
        selection_plan_id = plan_id or new_id()
        now = created_at or utc_now()
        with self.transaction() as connection:
            # The standing acceptances are read, merged and written inside one
            # transaction. Reading them outside it let a later writer compute a
            # legal new version from a plan it had already been overtaken on,
            # dropping an acceptance with no error and no trace: the version
            # number is allocated here, so the unique constraint never fires.
            self._lock_application(connection, application_id)
            carried = self._standing_acceptances(
                connection,
                application_id,
                job_analysis_id,
                expected_selection_plan_id,
            )
            accepted_gaps = merge_accepted_gaps(carried, list(new_acceptances or []))
            existing = (
                connection.execute(
                    select(selection_plans).where(selection_plans.c.id == selection_plan_id)
                )
                .mappings()
                .one_or_none()
            )
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
                    "accepted_gaps": accepted_gaps,
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
                accepted_gaps=accepted_gaps,
            )
            row = (
                connection.execute(
                    select(selection_plans).where(selection_plans.c.id == selection_plan_id)
                )
                .mappings()
                .one_or_none()
            )
        return self._selection_plan_record(row)

    def lock_application(self, application_id: str) -> None:
        """Take the Application lock before this unit of work reads anything.

        A unit of work runs at REPEATABLE READ, so its snapshot is fixed by its
        first statement. Locking later means reading under a snapshot taken
        before the lock was available: the waiting writer then finds the row
        updated by whoever held it and fails to serialize, and any version
        number it allocated from that snapshot is already stale. Taken first,
        the snapshot begins where the lock does.
        """
        with self.transaction() as connection:
            self._lock_application(connection, application_id)

    @staticmethod
    def _lock_application(connection: Connection, application_id: str) -> None:
        """Serialize every plan write for one Application.

        Reading the standing acceptances inside the transaction is not enough:
        the default isolation is READ COMMITTED, so two transactions can both
        read version 3, both pass the expected-plan check, and then write
        versions 4 and 5 - the later one merging onto a plan that no longer
        exists and dropping the earlier acceptance with no error.

        The version number is allocated here too, so the unique constraint never
        fires. `FOR UPDATE` on the owning Application row is what actually makes
        read, merge and allocate one atomic step, and every writer must take it
        - a path that skips the lock is not serialized by the others taking it.
        """
        connection.execute(
            select(applications.c.id).where(applications.c.id == application_id).with_for_update()
        ).one_or_none()

    def _active_plan(
        self,
        connection: Connection,
        application_id: str,
        expected_selection_plan_id: str | None,
    ) -> SelectionPlan | None:
        """The active plan, refusing if it moved since the decision was made.

        `expected_selection_plan_id` is the optimistic check: it is the plan the
        user was looking at when they decided. If the active plan has moved on,
        the command is refused rather than quietly rebased onto something the
        user never saw. One implementation, because both plan writers make the
        same promise about it.
        """
        row = (
            connection.execute(
                select(selection_plans)
                .where(selection_plans.c.application_id == application_id)
                .order_by(selection_plans.c.version_number.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        latest = self._selection_plan_record(row) if row is not None else None
        if expected_selection_plan_id is not None and (
            latest is None or latest.id != expected_selection_plan_id
        ):
            raise StateConflict(
                "the active SelectionPlan moved since this decision was made: expected "
                f"{expected_selection_plan_id}, found {latest.id if latest else 'none'}"
            )
        return latest

    def _standing_acceptances(
        self,
        connection: Connection,
        application_id: str,
        job_analysis_id: str,
        expected_selection_plan_id: str | None,
    ) -> list[AcceptedGap]:
        """The acceptances the next plan version inherits, read under the write.

        Inherited only from a plan for the *same* analysis. An acceptance is a
        decision about the gaps as one analysis stated them, so carrying it
        onto a plan for a different analysis would report a decision the user
        never made.
        """
        latest = self._active_plan(connection, application_id, expected_selection_plan_id)
        if latest is None or latest.job_analysis_id != job_analysis_id:
            return []
        return list(latest.accepted_gaps)

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
        *,
        accepted_gaps: list[AcceptedGap],
    ) -> None:
        analysis = (
            connection.execute(
                select(job_analyses.c.application_id).where(job_analyses.c.id == job_analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        if analysis is None or analysis["application_id"] != application_id:
            raise LineageBroken(
                "a selection plan cannot reference a job analysis belonging to another application"
            )
        version = connection.execute(
            select(
                (func.coalesce(func.max(selection_plans.c.version_number), 0) + 1).label("version")
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
                accepted_gaps_json=[gap.model_dump(mode="json") for gap in accepted_gaps],
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
            accepted_gaps=[
                AcceptedGap.model_validate(gap) for gap in record.get("accepted_gaps_json") or []
            ],
            created_at=record["created_at"],
        )

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(selection_plans).where(selection_plans.c.id == selection_plan_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no selection plan {selection_plan_id}")
        return self._selection_plan_record(row)

    def latest_selection_plan(self, application_id: str) -> SelectionPlan:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(selection_plans)
                    .where(selection_plans.c.application_id == application_id)
                    .order_by(selection_plans.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
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
            row = (
                connection.execute(select(job_analyses).where(job_analyses.c.id == analysis_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return self._analysis_record(row)

    def analyses(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(job_analyses)
                    .where(job_analyses.c.application_id == application_id)
                    .order_by(job_analyses.c.version_number)
                )
                .mappings()
                .all()
            )
        return [self._analysis_record(row) for row in rows]

    def latest_analysis(self, application_id: str) -> tuple[str, JobAnalysis]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(job_analyses.c.id, job_analyses.c.structured_json)
                    .where(job_analyses.c.application_id == application_id)
                    .order_by(job_analyses.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no analysis for application {application_id}")
        return row["id"], JobAnalysis.model_validate(row["structured_json"])
