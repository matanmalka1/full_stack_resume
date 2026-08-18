from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.models import ApplicationStatus
from ...domain.recruitment import transition_allowed
from ...util import canonical_json, utc_now
from .base import SqliteRepositoryBase
from .primitives import new_id


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
            self._insert_status_history(
                connection,
                application_id,
                None,
                ApplicationStatus.SAVED.value,
                created_at,
                "application created",
            )

    @staticmethod
    def _insert_status_history(
        connection: Any,
        application_id: str,
        from_status: str | None,
        to_status: str,
        changed_at: str,
        reason: str,
    ) -> None:
        connection.execute(
            "INSERT INTO status_history(application_id, from_status, to_status, changed_at, reason) "
            "VALUES(?, ?, ?, ?, ?)",
            (application_id, from_status, to_status, changed_at, reason),
        )

    def _set_status(
        self,
        connection: Any,
        application_id: str,
        current: ApplicationStatus,
        target: ApplicationStatus,
        now: str,
        reason: str,
    ) -> None:
        connection.execute(
            "UPDATE applications SET current_status=?, updated_at=? WHERE id=?",
            (target.value, now, application_id),
        )
        self._insert_status_history(
            connection, application_id, current.value, target.value, now, reason
        )

    def get_application(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id=?", (application_id,)
            ).fetchone()
        if row is None:
            raise KeyError(application_id)
        return dict(row)

    def list_applications(self) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM applications ORDER BY created_at, id"
                )
            ]

    def transition_status(
        self,
        application_id: str,
        target: ApplicationStatus | str,
        reason: str = "",
    ) -> None:
        target_status = ApplicationStatus(target)
        if target_status is ApplicationStatus.READY:
            raise ValueError(
                "ready is an engine-owned state derived from a passing render/ready "
                "pipeline; it cannot be set through the generic status transition. "
                "Use the render pipeline (Engine.render)."
            )
        if target_status is ApplicationStatus.APPLIED:
            raise ValueError(
                "applied is submission-owned; it can only be reached through "
                "Engine.submit(), which performs fresh ready integrity verification "
                "and binds the submission to the exact validated PDF artifact version. "
                "The generic status transition never accepts applied, even with a real "
                "rendered PDF artifact version id, because it cannot perform that "
                "verification itself."
            )
        now = utc_now()
        with self.transaction() as connection:
            self._transition_status(
                connection, application_id, target_status, reason, now
            )

    def _transition_status(
        self,
        connection: Any,
        application_id: str,
        target_status: ApplicationStatus,
        reason: str,
        now: str,
    ) -> None:
        """Apply one domain-approved transition on the caller's transaction."""
        row = connection.execute(
            "SELECT current_status FROM applications WHERE id=?", (application_id,)
        ).fetchone()
        if row is None:
            raise KeyError(application_id)
        current = ApplicationStatus(row["current_status"])
        if target_status is current:
            return
        if not transition_allowed(current, target_status):
            raise ValueError(
                f"invalid status transition: {current.value} -> {target_status.value}"
            )
        self._set_status(
            connection, application_id, current, target_status, now, reason
        )

    def record_event(
        self, application_id: str, event_type: str, payload: dict[str, Any]
    ) -> str:
        event_id = new_id()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO application_events(id, application_id, event_type, payload_json, created_at) "
                "VALUES(?, ?, ?, ?, ?)",
                (event_id, application_id, event_type, canonical_json(payload), utc_now()),
            )
        return event_id

    def set_next_action(
        self, application_id: str, action: str | None, action_date: str | None
    ) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                "UPDATE applications SET next_action=?, next_action_date=?, updated_at=? WHERE id=?",
                (action, action_date, utc_now(), application_id),
            )
            if result.rowcount != 1:
                raise KeyError(application_id)
        self.record_event(
            application_id,
            "next_action_set",
            {"next_action": action, "next_action_date": action_date},
        )

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                "UPDATE applications SET normalized_role=?, updated_at=? WHERE id=?",
                (normalized_role, utc_now(), application_id),
            )
            if result.rowcount != 1:
                raise KeyError(application_id)
