from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select, update

from ...application.errors import (
    VALIDATION_STALE,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ...domain.contracts.drafts import (
    DraftDocument,
    WorkingDraft,
)
from ...domain.contracts.records import ApprovedRevision
from ...domain.contracts.validation import ValidationReport
from ...util import new_id, utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import (
    approved_revisions,
    job_analyses,
    selection_plans,
    validation_runs,
    working_drafts,
)


class SqlAlchemyDraftRepository(SqlAlchemyRepositoryBase):
    """The one mutable WorkingDraft record and its optimistic edit token."""

    @staticmethod
    def _record(row: Any) -> WorkingDraft:
        if row is None:
            raise UnknownRecord("working draft does not exist")
        record = dict(row)
        return WorkingDraft(
            id=record["id"],
            application_id=record["application_id"],
            job_analysis_id=record["job_analysis_id"],
            selection_plan_id=record["selection_plan_id"],
            parent_revision_id=record["parent_revision_id"],
            source=DraftDocument.model_validate(record["source_json"]),
            edit_version=record["edit_version"],
            content_hash=record["content_hash"],
            active=bool(record["active"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    @staticmethod
    def _revision_record(row: Any) -> ApprovedRevision:
        if row is None:
            raise UnknownRecord("approved revision does not exist")
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
            track_emphasis_dependencies=record["track_emphasis_dependencies_json"],
            validation_run_id=record["validation_run_id"],
            validator_versions=record["validator_versions_json"],
            decision_provenance=record["decision_provenance_json"],
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
        plan = (
            connection.execute(
                select(
                    selection_plans.c.application_id,
                    selection_plans.c.job_analysis_id,
                ).where(selection_plans.c.id == selection_plan_id)
            )
            .mappings()
            .one_or_none()
        )
        if (
            plan is None
            or plan["application_id"] != application_id
            or plan["job_analysis_id"] != job_analysis_id
        ):
            raise LineageBroken(
                "a working draft cannot reference a selection plan belonging to "
                "another application or analysis"
            )
        if source.application_id != application_id or source.job_analysis_id != job_analysis_id:
            raise LineageBroken(
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
                insert(working_drafts).values(
                    id=draft_id,
                    application_id=application_id,
                    job_analysis_id=job_analysis_id,
                    selection_plan_id=selection_plan_id,
                    parent_revision_id=parent_revision_id,
                    source_json=source.model_dump(mode="json"),
                    edit_version=1,
                    content_hash=source.content_hash,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            row = (
                connection.execute(select(working_drafts).where(working_drafts.c.id == draft_id))
                .mappings()
                .one_or_none()
            )
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
        expected_working_draft_id: str | None = None,
        expected_edit_version: int | None = None,
    ) -> WorkingDraft:
        """Create the active record or replace its source as a new edit.

        §14: a replacement names the exact draft version it is replacing, and then this
        addresses that record rather than whichever one happens to be active. The
        difference is not cosmetic - selecting by `application_id + active` meant a draft
        archived between the command and this write left no active row, and the branch
        below created a *new* draft with a new id in place of the replacement the user
        asked for. Naming it turns both that and a concurrent edit into `StateConflict`,
        which the Operation reports as `SOURCE_CHANGED` rather than overwriting.
        """
        now = updated_at or utc_now()
        with self.transaction() as connection:
            self._require_lineage(
                connection,
                application_id,
                job_analysis_id,
                selection_plan_id,
                source,
            )
            current = (
                connection.execute(
                    select(working_drafts).where(
                        working_drafts.c.application_id == application_id,
                        working_drafts.c.active.is_(True),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if expected_working_draft_id is not None:
                if current is None or current["id"] != expected_working_draft_id:
                    raise StateConflict(
                        f"working draft {expected_working_draft_id} is no longer the "
                        f"active draft of application {application_id}"
                    )
                if current["edit_version"] != expected_edit_version:
                    raise StateConflict(
                        f"working draft {expected_working_draft_id} is at edit version "
                        f"{current['edit_version']}, not {expected_edit_version}"
                    )
            if current is None:
                draft_id = new_id()
                connection.execute(
                    insert(working_drafts).values(
                        id=draft_id,
                        application_id=application_id,
                        job_analysis_id=job_analysis_id,
                        selection_plan_id=selection_plan_id,
                        parent_revision_id=parent_revision_id,
                        source_json=source.model_dump(mode="json"),
                        edit_version=1,
                        content_hash=source.content_hash,
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                draft_id = current["id"]
                # The version is in the WHERE, not only in the check above: the check
                # reads and the update writes, and a concurrent commit landing between
                # them must lose rather than be overwritten.
                result = connection.execute(
                    update(working_drafts)
                    .where(
                        working_drafts.c.id == draft_id,
                        working_drafts.c.active.is_(True),
                        *(
                            ()
                            if expected_edit_version is None
                            else (working_drafts.c.edit_version == expected_edit_version,)
                        ),
                    )
                    .values(
                        job_analysis_id=job_analysis_id,
                        selection_plan_id=selection_plan_id,
                        parent_revision_id=parent_revision_id,
                        source_json=source.model_dump(mode="json"),
                        edit_version=working_drafts.c.edit_version + 1,
                        content_hash=source.content_hash,
                        updated_at=now,
                    )
                )
                if expected_edit_version is not None and result.rowcount == 0:
                    raise StateConflict(
                        f"working draft {draft_id} changed before the replacement was committed"
                    )
            row = (
                connection.execute(select(working_drafts).where(working_drafts.c.id == draft_id))
                .mappings()
                .one_or_none()
            )
        return self._record(row)

    def working_draft(self, working_draft_id: str) -> WorkingDraft:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(working_drafts).where(working_drafts.c.id == working_draft_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no working draft {working_draft_id}")
        return self._record(row)

    def active_working_draft(self, application_id: str) -> WorkingDraft:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(working_drafts).where(
                        working_drafts.c.application_id == application_id,
                        working_drafts.c.active.is_(True),
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no active working draft for application {application_id}")
        return self._record(row)

    def update_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        source: DraftDocument,
        *,
        selection_plan_id: str | None = None,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        """One optimistic edit, optionally repointing the draft at a new plan.

        `selection_plan_id` exists for `apply_selection_change`, which has to
        create the immutable plan and move the draft onto it in one place: a
        draft still naming the previous plan while carrying the new plan's
        content would misdescribe its own lineage. Left unset, the draft keeps
        the plan it already had, which is every autosave.
        """
        now = updated_at or utc_now()
        with self.transaction() as connection:
            current = (
                connection.execute(
                    select(working_drafts).where(working_drafts.c.id == working_draft_id)
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise UnknownRecord(f"no working draft {working_draft_id}")
            plan_id = selection_plan_id or current["selection_plan_id"]
            self._require_lineage(
                connection,
                current["application_id"],
                current["job_analysis_id"],
                plan_id,
                source,
            )
            changed = connection.execute(
                update(working_drafts)
                .where(
                    working_drafts.c.id == working_draft_id,
                    working_drafts.c.edit_version == expected_version,
                    working_drafts.c.active.is_(True),
                )
                .values(
                    source_json=source.model_dump(mode="json"),
                    selection_plan_id=plan_id,
                    edit_version=working_drafts.c.edit_version + 1,
                    content_hash=source.content_hash,
                    updated_at=now,
                )
            )
            if changed.rowcount != 1:
                raise StateConflict("working draft edit version mismatch")
            row = (
                connection.execute(
                    select(working_drafts).where(working_drafts.c.id == working_draft_id)
                )
                .mappings()
                .one_or_none()
            )
        return self._record(row)

    def deactivate_working_draft(
        self,
        working_draft_id: str,
        expected_version: int,
        *,
        updated_at: str | None = None,
    ) -> WorkingDraft:
        """Clear the active pointer for one exact draft version.

        The version is part of the WHERE clause for the same reason it is on an
        edit: archiving a draft the caller has not seen the latest version of
        would discard an edit that arrived in between. The row survives - it is
        the historical record the ApprovedRevisions and ValidationRuns still
        reference - so this deactivates rather than deletes.
        """
        now = updated_at or utc_now()
        with self.transaction() as connection:
            current = (
                connection.execute(
                    select(working_drafts).where(working_drafts.c.id == working_draft_id)
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise UnknownRecord(f"no working draft {working_draft_id}")
            changed = connection.execute(
                update(working_drafts)
                .where(
                    working_drafts.c.id == working_draft_id,
                    working_drafts.c.edit_version == expected_version,
                    working_drafts.c.active.is_(True),
                )
                .values(active=False, updated_at=now)
            )
            if changed.rowcount != 1:
                raise StateConflict("working draft edit version mismatch")
            row = (
                connection.execute(
                    select(working_drafts).where(working_drafts.c.id == working_draft_id)
                )
                .mappings()
                .one_or_none()
            )
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
            row = (
                connection.execute(
                    select(
                        *working_drafts.c,
                        job_analyses.c.job_snapshot_id.label("frozen_job_snapshot_id"),
                        selection_plans.c.application_id.label("plan_application_id"),
                        selection_plans.c.job_analysis_id.label("plan_job_analysis_id"),
                        selection_plans.c.candidate_context_version,
                        selection_plans.c.candidate_context_hash,
                        selection_plans.c.profile_version,
                        selection_plans.c.selection_policy_version,
                        selection_plans.c.track_emphasis_dependencies_json,
                        validation_runs.c.application_id.label("validation_application_id"),
                        validation_runs.c.working_draft_id.label("validation_working_draft_id"),
                        validation_runs.c.edit_version.label("validation_edit_version"),
                        validation_runs.c.content_hash.label("validation_content_hash"),
                        validation_runs.c.job_snapshot_id.label("validation_job_snapshot_id"),
                        validation_runs.c.job_analysis_id.label("validation_job_analysis_id"),
                        validation_runs.c.selection_plan_id.label("validation_selection_plan_id"),
                        validation_runs.c.knowledge_context_hash,
                        validation_runs.c.validator_versions_json,
                        validation_runs.c.report_json,
                    )
                    .select_from(
                        working_drafts.join(
                            job_analyses,
                            job_analyses.c.id == working_drafts.c.job_analysis_id,
                        )
                        .join(
                            selection_plans,
                            selection_plans.c.id == working_drafts.c.selection_plan_id,
                        )
                        .join(validation_runs, validation_runs.c.id == validation_run_id)
                    )
                    .where(working_drafts.c.id == working_draft_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise PreconditionFailed(
                    "approval requires an existing working draft and validation"
                )
            if (
                row["application_id"] != application_id
                or row["plan_application_id"] != application_id
                or row["validation_application_id"] != application_id
            ):
                raise LineageBroken("approval lineage belongs to another application")
            if not row["active"]:
                raise PreconditionFailed("approval requires the active working draft")
            if (
                row["plan_job_analysis_id"] != row["job_analysis_id"]
                or row["validation_working_draft_id"] != working_draft_id
                or row["validation_edit_version"] != row["edit_version"]
                or row["validation_content_hash"] != row["content_hash"]
                or row["validation_job_snapshot_id"] != row["frozen_job_snapshot_id"]
                or row["validation_job_analysis_id"] != row["job_analysis_id"]
                or row["validation_selection_plan_id"] != row["selection_plan_id"]
            ):
                raise PreconditionFailed(
                    "approval validation does not match the exact working draft",
                    code=VALIDATION_STALE,
                )
            if not ValidationReport.model_validate(row["report_json"]).passed:
                raise ValidationBlocked("approval requires a passing validation run")

            source = DraftDocument.model_validate(row["source_json"])
            version = connection.execute(
                select(
                    (func.coalesce(func.max(approved_revisions.c.version_number), 0) + 1).label(
                        "version"
                    )
                ).where(approved_revisions.c.application_id == application_id)
            ).scalar_one()
            connection.execute(
                insert(approved_revisions).values(
                    id=revision_id,
                    application_id=application_id,
                    version_number=version,
                    job_snapshot_id=row["frozen_job_snapshot_id"],
                    job_analysis_id=row["job_analysis_id"],
                    selection_plan_id=row["selection_plan_id"],
                    working_draft_id=working_draft_id,
                    draft_edit_version=row["edit_version"],
                    draft_content_hash=row["content_hash"],
                    resume_json_path=resume_json_reference,
                    resume_json_hash=resume_json_hash,
                    resume_markdown_path=resume_markdown_reference,
                    resume_markdown_hash=resume_markdown_hash,
                    candidate_context_version=row["candidate_context_version"],
                    candidate_context_hash=row["candidate_context_hash"],
                    facts_version=source.fact_store_version,
                    knowledge_context_hash=row["knowledge_context_hash"],
                    profile_version=row["profile_version"],
                    selection_policy_version=row["selection_policy_version"],
                    track_emphasis_dependencies_json=row["track_emphasis_dependencies_json"],
                    validation_run_id=validation_run_id,
                    validator_versions_json=row["validator_versions_json"],
                    decision_provenance_json=decision_provenance,
                    approved_at=approved_at,
                )
            )
            changed = connection.execute(
                update(working_drafts)
                .where(
                    working_drafts.c.id == working_draft_id,
                    working_drafts.c.active.is_(True),
                )
                .values(active=False, updated_at=approved_at)
            )
            if changed.rowcount != 1:
                raise StateConflict("working draft changed before approval committed")
            revision = (
                connection.execute(
                    select(approved_revisions).where(approved_revisions.c.id == revision_id)
                )
                .mappings()
                .one_or_none()
            )
        return self._revision_record(revision)

    def approved_revision(self, revision_id: str) -> ApprovedRevision:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(approved_revisions).where(approved_revisions.c.id == revision_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no approved revision {revision_id}")
        return self._revision_record(row)

    def latest_approved_revision(self, application_id: str) -> ApprovedRevision:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(approved_revisions)
                    .where(approved_revisions.c.application_id == application_id)
                    .order_by(approved_revisions.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(f"no approved revision for application {application_id}")
        return self._revision_record(row)

    def approved_revisions(self, application_id: str) -> list[ApprovedRevision]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(approved_revisions)
                    .where(approved_revisions.c.application_id == application_id)
                    .order_by(approved_revisions.c.version_number)
                )
                .mappings()
                .all()
            )
        return [self._revision_record(row) for row in rows]
