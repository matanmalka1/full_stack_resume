from __future__ import annotations

import json
from typing import Any

from ...domain.models import ApprovedRevision, DraftDocument, ValidationReport, WorkingDraft
from ...util import canonical_json, utc_now
from .base import SqliteRepositoryBase
from .primitives import new_id


class SqliteDraftRepository(SqliteRepositoryBase):
    """The one mutable WorkingDraft record and its optimistic edit token."""

    @staticmethod
    def _record(row: Any) -> WorkingDraft:
        if row is None:
            raise KeyError("working draft does not exist")
        record = dict(row)
        return WorkingDraft(
            id=record["id"],
            application_id=record["application_id"],
            job_analysis_id=record["job_analysis_id"],
            selection_plan_id=record["selection_plan_id"],
            parent_revision_id=record["parent_revision_id"],
            source=DraftDocument.model_validate_json(record["source_json"]),
            edit_version=record["edit_version"],
            content_hash=record["content_hash"],
            active=bool(record["active"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    @staticmethod
    def _revision_record(row: Any) -> ApprovedRevision:
        if row is None:
            raise KeyError("approved revision does not exist")
        record = dict(row)
        return ApprovedRevision(
            id=record["id"],
            application_id=record["application_id"],
            version_number=record["version_number"],
            job_snapshot_id=record["job_snapshot_id"],
            job_analysis_id=record["job_analysis_id"],
            selection_plan_id=record["selection_plan_id"],
            working_draft_id=record["working_draft_id"],
            draft_edit_version=record["draft_edit_version"],
            draft_content_hash=record["draft_content_hash"],
            resume_json_reference=record["resume_json_path"],
            resume_json_hash=record["resume_json_hash"],
            resume_markdown_reference=record["resume_markdown_path"],
            resume_markdown_hash=record["resume_markdown_hash"],
            candidate_context_version=record["candidate_context_version"],
            candidate_context_hash=record["candidate_context_hash"],
            facts_version=record["facts_version"],
            knowledge_context_hash=record["knowledge_context_hash"],
            profile_version=record["profile_version"],
            selection_policy_version=record["selection_policy_version"],
            track_emphasis_dependencies=json.loads(record["track_emphasis_dependencies_json"]),
            validation_run_id=record["validation_run_id"],
            validator_versions=json.loads(record["validator_versions_json"]),
            decision_provenance=json.loads(record["decision_provenance_json"]),
            approved_at=record["approved_at"],
        )

    @staticmethod
    def _require_lineage(
        connection: Any,
        application_id: str,
        job_analysis_id: str,
        selection_plan_id: str,
        source: DraftDocument,
    ) -> None:
        plan = connection.execute(
            "SELECT application_id, job_analysis_id FROM selection_plans WHERE id=?",
            (selection_plan_id,),
        ).fetchone()
        if (
            plan is None
            or plan["application_id"] != application_id
            or plan["job_analysis_id"] != job_analysis_id
        ):
            raise ValueError(
                "a working draft cannot reference a selection plan belonging to "
                "another application or analysis"
            )
        if source.application_id != application_id or source.job_analysis_id != job_analysis_id:
            raise ValueError("a working draft source must match its application and job analysis")

    def create_working_draft(
        self,
        application_id: str,
        job_analysis_id: str,
        selection_plan_id: str,
        source: DraftDocument,
        *,
        parent_revision_id: str | None = None,
        working_draft_id: str | None = None,
        created_at: str | None = None,
    ) -> WorkingDraft:
        draft_id = working_draft_id or new_id()
        now = created_at or utc_now()
        with self.transaction() as connection:
            self._require_lineage(
                connection,
                application_id,
                job_analysis_id,
                selection_plan_id,
                source,
            )
            connection.execute(
                "INSERT INTO working_drafts(id, application_id, job_analysis_id, "
                "selection_plan_id, parent_revision_id, source_json, edit_version, "
                "content_hash, active, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, 1, ?, 1, ?, ?)",
                (
                    draft_id,
                    application_id,
                    job_analysis_id,
                    selection_plan_id,
                    parent_revision_id,
                    canonical_json(source.model_dump(mode="json")),
                    source.content_hash,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM working_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        return self._record(row)

    def replace_active_working_draft(
        self,
        application_id: str,
        job_analysis_id: str,
        selection_plan_id: str,
        source: DraftDocument,
        *,
        parent_revision_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        """Create the active record or replace its source as a new edit."""
        now = updated_at or utc_now()
        with self.transaction() as connection:
            self._require_lineage(
                connection,
                application_id,
                job_analysis_id,
                selection_plan_id,
                source,
            )
            current = connection.execute(
                "SELECT * FROM working_drafts WHERE application_id=? AND active=1",
                (application_id,),
            ).fetchone()
            if current is None:
                draft_id = new_id()
                connection.execute(
                    "INSERT INTO working_drafts(id, application_id, job_analysis_id, "
                    "selection_plan_id, parent_revision_id, source_json, edit_version, "
                    "content_hash, active, created_at, updated_at) "
                    "VALUES(?, ?, ?, ?, ?, ?, 1, ?, 1, ?, ?)",
                    (
                        draft_id,
                        application_id,
                        job_analysis_id,
                        selection_plan_id,
                        parent_revision_id,
                        canonical_json(source.model_dump(mode="json")),
                        source.content_hash,
                        now,
                        now,
                    ),
                )
            else:
                draft_id = current["id"]
                connection.execute(
                    "UPDATE working_drafts SET job_analysis_id=?, selection_plan_id=?, "
                    "parent_revision_id=?, source_json=?, edit_version=edit_version+1, "
                    "content_hash=?, updated_at=? WHERE id=? AND active=1",
                    (
                        job_analysis_id,
                        selection_plan_id,
                        parent_revision_id,
                        canonical_json(source.model_dump(mode="json")),
                        source.content_hash,
                        now,
                        draft_id,
                    ),
                )
            row = connection.execute(
                "SELECT * FROM working_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        return self._record(row)

    def working_draft(self, working_draft_id: str) -> WorkingDraft:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM working_drafts WHERE id=?", (working_draft_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"no working draft {working_draft_id}")
        return self._record(row)

    def active_working_draft(self, application_id: str) -> WorkingDraft:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM working_drafts WHERE application_id=? AND active=1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no active working draft for application {application_id}")
        return self._record(row)

    def update_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        now = updated_at or utc_now()
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT * FROM working_drafts WHERE id=?", (working_draft_id,)
            ).fetchone()
            if current is None:
                raise KeyError(f"no working draft {working_draft_id}")
            self._require_lineage(
                connection,
                current["application_id"],
                current["job_analysis_id"],
                current["selection_plan_id"],
                source,
            )
            changed = connection.execute(
                "UPDATE working_drafts SET source_json=?, edit_version=edit_version+1, "
                "content_hash=?, updated_at=? "
                "WHERE id=? AND edit_version=? AND active=1",
                (
                    canonical_json(source.model_dump(mode="json")),
                    source.content_hash,
                    now,
                    working_draft_id,
                    expected_version,
                ),
            )
            if changed.rowcount != 1:
                raise ValueError("working draft edit version mismatch")
            row = connection.execute(
                "SELECT * FROM working_drafts WHERE id=?", (working_draft_id,)
            ).fetchone()
        return self._record(row)

    def create_approved_revision(
        self,
        application_id: str,
        revision_id: str,
        working_draft_id: str,
        validation_run_id: str,
        resume_json_reference: str,
        resume_json_hash: str,
        resume_markdown_reference: str,
        resume_markdown_hash: str,
        decision_provenance: dict[str, str],
        *,
        approved_at: str,
    ) -> ApprovedRevision:
        """Freeze one exact WorkingDraft using its recorded plan and validation."""
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT wd.*, ja.job_snapshot_id AS frozen_job_snapshot_id, "
                "sp.application_id AS plan_application_id, "
                "sp.job_analysis_id AS plan_job_analysis_id, "
                "sp.candidate_context_version, sp.candidate_context_hash, "
                "sp.profile_version, sp.selection_policy_version, "
                "sp.track_emphasis_dependencies_json, "
                "vr.application_id AS validation_application_id, "
                "vr.working_draft_id AS validation_working_draft_id, "
                "vr.edit_version AS validation_edit_version, "
                "vr.content_hash AS validation_content_hash, "
                "vr.job_snapshot_id AS validation_job_snapshot_id, "
                "vr.job_analysis_id AS validation_job_analysis_id, "
                "vr.selection_plan_id AS validation_selection_plan_id, "
                "vr.knowledge_context_hash, vr.validator_versions_json, vr.report_json "
                "FROM working_drafts wd "
                "JOIN job_analyses ja ON ja.id=wd.job_analysis_id "
                "JOIN selection_plans sp ON sp.id=wd.selection_plan_id "
                "JOIN validation_runs vr ON vr.id=? "
                "WHERE wd.id=?",
                (validation_run_id, working_draft_id),
            ).fetchone()
            if row is None:
                raise ValueError("approval requires an existing working draft and validation")
            if (
                row["application_id"] != application_id
                or row["plan_application_id"] != application_id
                or row["validation_application_id"] != application_id
            ):
                raise ValueError("approval lineage belongs to another application")
            if not row["active"]:
                raise ValueError("approval requires the active working draft")
            if (
                row["plan_job_analysis_id"] != row["job_analysis_id"]
                or row["validation_working_draft_id"] != working_draft_id
                or row["validation_edit_version"] != row["edit_version"]
                or row["validation_content_hash"] != row["content_hash"]
                or row["validation_job_snapshot_id"] != row["frozen_job_snapshot_id"]
                or row["validation_job_analysis_id"] != row["job_analysis_id"]
                or row["validation_selection_plan_id"] != row["selection_plan_id"]
            ):
                raise ValueError("approval validation does not match the exact working draft")
            if not ValidationReport.model_validate_json(row["report_json"]).passed:
                raise ValueError("approval requires a passing validation run")

            source = DraftDocument.model_validate_json(row["source_json"])
            version = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS version "
                "FROM approved_revisions WHERE application_id=?",
                (application_id,),
            ).fetchone()["version"]
            connection.execute(
                "INSERT INTO approved_revisions("
                "id, application_id, version_number, job_snapshot_id, job_analysis_id, "
                "selection_plan_id, working_draft_id, draft_edit_version, "
                "draft_content_hash, resume_json_path, resume_json_hash, "
                "resume_markdown_path, resume_markdown_hash, candidate_context_version, "
                "candidate_context_hash, facts_version, knowledge_context_hash, "
                "profile_version, selection_policy_version, "
                "track_emphasis_dependencies_json, validation_run_id, "
                "validator_versions_json, decision_provenance_json, approved_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    revision_id,
                    application_id,
                    version,
                    row["frozen_job_snapshot_id"],
                    row["job_analysis_id"],
                    row["selection_plan_id"],
                    working_draft_id,
                    row["edit_version"],
                    row["content_hash"],
                    resume_json_reference,
                    resume_json_hash,
                    resume_markdown_reference,
                    resume_markdown_hash,
                    row["candidate_context_version"],
                    row["candidate_context_hash"],
                    source.fact_store_version,
                    row["knowledge_context_hash"],
                    row["profile_version"],
                    row["selection_policy_version"],
                    row["track_emphasis_dependencies_json"],
                    validation_run_id,
                    row["validator_versions_json"],
                    canonical_json(decision_provenance),
                    approved_at,
                ),
            )
            changed = connection.execute(
                "UPDATE working_drafts SET active=0, updated_at=? WHERE id=? AND active=1",
                (approved_at, working_draft_id),
            )
            if changed.rowcount != 1:
                raise ValueError("working draft changed before approval committed")
            revision = connection.execute(
                "SELECT * FROM approved_revisions WHERE id=?", (revision_id,)
            ).fetchone()
        return self._revision_record(revision)

    def approved_revision(self, revision_id: str) -> ApprovedRevision:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM approved_revisions WHERE id=?", (revision_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"no approved revision {revision_id}")
        return self._revision_record(row)

    def latest_approved_revision(self, application_id: str) -> ApprovedRevision:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM approved_revisions WHERE application_id=? "
                "ORDER BY version_number DESC LIMIT 1",
                (application_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"no approved revision for application {application_id}")
        return self._revision_record(row)
