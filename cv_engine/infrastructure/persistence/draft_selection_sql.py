from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from ...application.errors import LineageBroken, StateConflict, UnknownRecord
from ...domain.contracts.drafts import DraftDocument, WorkingDraft
from ...util import utc_now
from .tables import selection_plans, working_drafts


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
        raise LineageBroken("a working draft source must match its application and job analysis")


def _update_working_draft(
    connection: Connection,
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
    current = (
        connection.execute(select(working_drafts).where(working_drafts.c.id == working_draft_id))
        .mappings()
        .one_or_none()
    )
    if current is None:
        raise UnknownRecord(f"no working draft {working_draft_id}")
    plan_id = selection_plan_id or current["selection_plan_id"]
    _require_lineage(
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
        connection.execute(select(working_drafts).where(working_drafts.c.id == working_draft_id))
        .mappings()
        .one_or_none()
    )
    return _record(row)
