from __future__ import annotations

from typing import Any

from ...application.errors import UnknownRecord
from ...domain.models import ApplicationStatus
from ...util import canonical_json, new_id, utc_now
from .base import SqliteRepositoryBase


class SqliteApplicationRepository(SqliteRepositoryBase):
    def _insert_application(
        self,
        *,
        application_id: str,
        company: str,
        target_role: str,
        source_url: str | None,
        notes: str,
        source: str,
        created_at: str,
        actor_type: str,
        client: str,
        installation_id: str,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO applications(id, company, target_role, source_url, current_status, notes, source, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    application_id,
                    company.strip(),
                    target_role.strip(),
                    source_url,
                    ApplicationStatus.SAVED.value,
                    notes,
                    source,
                    created_at,
                    created_at,
                ),
            )
            connection.execute(
                "INSERT INTO recruitment_events(id, application_id, event_type, from_status, "
                "to_status, reason, actor_type, client, installation_id, occurred_at, "
                "payload_json, created_at) VALUES(?, ?, 'status_transition', NULL, 'saved', "
                "'application created', ?, ?, ?, ?, '{}', ?)",
                (
                    new_id(),
                    application_id,
                    actor_type,
                    client,
                    installation_id,
                    created_at,
                    created_at,
                ),
            )

    def get_application(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id=?", (application_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def list_applications(self) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            return [
                dict(row)
                for row in connection.execute("SELECT * FROM applications ORDER BY created_at, id")
            ]

    def record_event(self, application_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = new_id()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO application_events(id, application_id, event_type, payload_json, created_at) "
                "VALUES(?, ?, ?, ?, ?)",
                (event_id, application_id, event_type, canonical_json(payload), utc_now()),
            )
        return event_id

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                "UPDATE applications SET normalized_role=?, updated_at=? WHERE id=?",
                (normalized_role, utc_now(), application_id),
            )
            if result.rowcount != 1:
                raise UnknownRecord(application_id)
