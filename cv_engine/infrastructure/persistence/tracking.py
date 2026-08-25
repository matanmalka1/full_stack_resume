from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from ...application.errors import (
    LineageBroken,
    StateConflict,
    UnknownRecord,
)
from ...util import canonical_json, new_id
from .base import SqlAlchemyRepositoryBase
from .tables import applications, recruitment_events, submissions

_RECRUITMENT_EVENT_COLUMNS = tuple(
    column for column in recruitment_events.c if column.name != "seq"
)
_SUBMISSION_COLUMNS = tuple(column for column in submissions.c if column.name != "seq")


def _json_text_record(row: Any, field: str) -> dict[str, Any]:
    record = dict(row)
    record[field] = canonical_json(record[field])
    return record


class SqlAlchemyTrackingRepository(SqlAlchemyRepositoryBase):
    def insert_submission(
        self,
        submission_id: str,
        application_id: str,
        submission_type: str,
        approved_revision_id: str | None,
        artifact_version_id: str | None,
        submitted_at: str,
        metadata: dict[str, Any],
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                insert(submissions).values(
                    id=submission_id,
                    application_id=application_id,
                    submission_type=submission_type,
                    approved_revision_id=approved_revision_id,
                    artifact_version_id=artifact_version_id,
                    submitted_at=submitted_at,
                    metadata_json=metadata,
                )
            )

    def insert_recruitment_event(
        self,
        *,
        application_id: str,
        expected_current_status: str,
        target_status: str,
        event_type: str,
        reason: str,
        actor_type: str,
        client: str,
        installation_id: str,
        occurred_at: str,
        terminal_outcome: str | None,
        corrects_event_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str:
        identity = event_id or new_id()
        with self.transaction() as connection:
            row = (
                connection.execute(
                    select(applications.c.current_status, applications.c.terminal_outcome).where(
                        applications.c.id == application_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise UnknownRecord(application_id)
            if row["current_status"] != expected_current_status:
                raise StateConflict(
                    "application status changed before commit: "
                    f"expected {expected_current_status}, found {row['current_status']}"
                )
            if corrects_event_id is not None:
                corrected = (
                    connection.execute(
                        select(recruitment_events.c.application_id).where(
                            recruitment_events.c.id == corrects_event_id
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if corrected is None:
                    raise UnknownRecord(corrects_event_id)
                if corrected["application_id"] != application_id:
                    raise LineageBroken("a correction cannot reference another application's event")
            connection.execute(
                update(applications)
                .where(applications.c.id == application_id)
                .values(
                    current_status=target_status,
                    terminal_outcome=terminal_outcome,
                    updated_at=occurred_at,
                )
            )
            connection.execute(
                insert(recruitment_events).values(
                    id=identity,
                    application_id=application_id,
                    event_type=event_type,
                    from_status=expected_current_status,
                    to_status=target_status,
                    corrects_event_id=corrects_event_id,
                    reason=reason,
                    actor_type=actor_type,
                    client=client,
                    installation_id=installation_id,
                    occurred_at=occurred_at,
                    payload_json=payload or {},
                    created_at=occurred_at,
                )
            )
        return identity

    def insert_next_action_event(
        self,
        *,
        application_id: str,
        next_action: str | None,
        next_action_date: str | None,
        actor_type: str,
        client: str,
        installation_id: str,
        occurred_at: str,
    ) -> str:
        event_id = new_id()
        with self.transaction() as connection:
            row = (
                connection.execute(
                    select(applications.c.current_status).where(applications.c.id == application_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise UnknownRecord(application_id)
            connection.execute(
                update(applications)
                .where(applications.c.id == application_id)
                .values(
                    next_action=next_action,
                    next_action_date=next_action_date,
                    updated_at=occurred_at,
                )
            )
            connection.execute(
                insert(recruitment_events).values(
                    id=event_id,
                    application_id=application_id,
                    event_type="next_action",
                    from_status=row["current_status"],
                    to_status=row["current_status"],
                    reason="",
                    actor_type=actor_type,
                    client=client,
                    installation_id=installation_id,
                    occurred_at=occurred_at,
                    payload_json={
                        "next_action": next_action,
                        "next_action_date": next_action_date,
                    },
                    created_at=occurred_at,
                )
            )
        return event_id

    def recruitment_event(self, event_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(*_RECRUITMENT_EVENT_COLUMNS).where(recruitment_events.c.id == event_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(event_id)
        return _json_text_record(row, "payload_json")

    def recruitment_events(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(*_RECRUITMENT_EVENT_COLUMNS)
                    .where(recruitment_events.c.application_id == application_id)
                    .order_by(recruitment_events.c.occurred_at, recruitment_events.c.seq)
                )
                .mappings()
                .all()
            )
        return [_json_text_record(row, "payload_json") for row in rows]

    def submissions(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(*_SUBMISSION_COLUMNS)
                    .where(submissions.c.application_id == application_id)
                    .order_by(submissions.c.submitted_at, submissions.c.seq)
                )
                .mappings()
                .all()
            )
        return [_json_text_record(row, "metadata_json") for row in rows]
