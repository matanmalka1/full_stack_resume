from __future__ import annotations

from typing import Any

from ...domain.models import DraftDocument, WorkingDraft
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
        if (
            source.application_id != application_id
            or source.job_analysis_id != job_analysis_id
        ):
            raise ValueError(
                "a working draft source must match its application and job analysis"
            )

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
