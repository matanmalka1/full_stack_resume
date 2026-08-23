from __future__ import annotations

from typing import Any

from ...application.errors import (
    LineageBroken,
    StateConflict,
    UnknownRecord,
)
from ...util import canonical_json, new_id
from .base import SqliteRepositoryBase


class SqliteTrackingRepository(SqliteRepositoryBase):
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
                "INSERT INTO submissions(id, application_id, submission_type, "
                "approved_revision_id, artifact_version_id, submitted_at, metadata_json) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    submission_id,
                    application_id,
                    submission_type,
                    approved_revision_id,
                    artifact_version_id,
                    submitted_at,
                    canonical_json(metadata),
                ),
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
            row = connection.execute(
                "SELECT current_status, terminal_outcome FROM applications WHERE id=?",
                (application_id,),
            ).fetchone()
            if row is None:
                raise UnknownRecord(application_id)
            if row["current_status"] != expected_current_status:
                raise StateConflict(
                    "application status changed before commit: "
                    f"expected {expected_current_status}, found {row['current_status']}"
                )
            if corrects_event_id is not None:
                corrected = connection.execute(
                    "SELECT application_id FROM recruitment_events WHERE id=?",
                    (corrects_event_id,),
                ).fetchone()
                if corrected is None:
                    raise UnknownRecord(corrects_event_id)
                if corrected["application_id"] != application_id:
                    raise LineageBroken("a correction cannot reference another application's event")
            connection.execute(
                "UPDATE applications SET current_status=?, terminal_outcome=?, updated_at=? "
                "WHERE id=?",
                (target_status, terminal_outcome, occurred_at, application_id),
            )
            connection.execute(
                "INSERT INTO recruitment_events(id, application_id, event_type, from_status, "
                "to_status, corrects_event_id, reason, actor_type, client, installation_id, "
                "occurred_at, payload_json, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    identity,
                    application_id,
                    event_type,
                    expected_current_status,
                    target_status,
                    corrects_event_id,
                    reason,
                    actor_type,
                    client,
                    installation_id,
                    occurred_at,
                    canonical_json(payload or {}),
                    occurred_at,
                ),
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
            row = connection.execute(
                "SELECT current_status FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            if row is None:
                raise UnknownRecord(application_id)
            connection.execute(
                "UPDATE applications SET next_action=?, next_action_date=?, updated_at=? WHERE id=?",
                (next_action, next_action_date, occurred_at, application_id),
            )
            connection.execute(
                "INSERT INTO recruitment_events(id, application_id, event_type, from_status, "
                "to_status, reason, actor_type, client, installation_id, occurred_at, "
                "payload_json, created_at) VALUES(?, ?, 'next_action', ?, ?, '', ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    application_id,
                    row["current_status"],
                    row["current_status"],
                    actor_type,
                    client,
                    installation_id,
                    occurred_at,
                    canonical_json(
                        {"next_action": next_action, "next_action_date": next_action_date}
                    ),
                    occurred_at,
                ),
            )
        return event_id

    def recruitment_event(self, event_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM recruitment_events WHERE id=?", (event_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord(event_id)
        return dict(row)

    def recruitment_events(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM recruitment_events WHERE application_id=? "
                "ORDER BY occurred_at, rowid",
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def submissions(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM submissions WHERE application_id=? ORDER BY submitted_at, rowid",
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]
