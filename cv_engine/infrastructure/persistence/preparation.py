from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select

from ...application.errors import (
    UnknownRecord,
)
from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.selection import (
    SelectionManifest,
    SelectionPlan,
)
from ...util import canonical_json, new_id, utc_now
from .analysis_sql import _analysis_record, _create_selection_plan, _selection_plan_record
from .base import SqlAlchemyRepositoryBase
from .tables import job_analyses, job_snapshots, selection_plans


def _snapshot_record(row: Any) -> dict[str, Any]:
    record = dict(row)
    record["source_metadata_json"] = canonical_json(record["source_metadata_json"])
    return record


class SqlAlchemyPreparationRepository(SqlAlchemyRepositoryBase):
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

    def job_snapshots(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(job_snapshots)
                    .where(job_snapshots.c.application_id == application_id)
                    .order_by(job_snapshots.c.version_number)
                )
                .mappings()
                .all()
            )
        return [_snapshot_record(row) for row in rows]

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
        expected_selection_plan_id: str | None = None,
        enforce_expected_selection_plan: bool = False,
        refuse_matching_context_operation: bool = False,
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan:
        with self.transaction() as connection:
            return _create_selection_plan(
                connection,
                application_id,
                job_analysis_id,
                plan,
                candidate_context_version=candidate_context_version,
                candidate_context_hash=candidate_context_hash,
                profile_version=profile_version,
                selection_policy_version=selection_policy_version,
                track_emphasis_dependencies=track_emphasis_dependencies,
                expected_selection_plan_id=expected_selection_plan_id,
                enforce_expected_selection_plan=enforce_expected_selection_plan,
                refuse_matching_context_operation=refuse_matching_context_operation,
                plan_id=plan_id,
                created_at=created_at,
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
        return _selection_plan_record(row)

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
        return _selection_plan_record(row)

    def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(select(job_analyses).where(job_analyses.c.id == analysis_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return _analysis_record(row)

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
        return [_analysis_record(row) for row in rows]

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
