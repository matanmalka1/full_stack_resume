from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from ...application.errors import UnknownRecord
from ...domain.models import ApplicationStatus
from ...util import new_id, utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import application_events, applications, recruitment_events


class SqlAlchemyApplicationRepository(SqlAlchemyRepositoryBase):
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
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                insert(applications).values(
                    id=application_id,
                    company=company.strip(),
                    target_role=target_role.strip(),
                    source_url=source_url,
                    current_status=ApplicationStatus.SAVED.value,
                    notes=notes,
                    source=source,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            connection.execute(
                insert(recruitment_events).values(
                    id=new_id(),
                    application_id=application_id,
                    event_type="status_transition",
                    from_status=None,
                    to_status="saved",
                    reason="application created",
                    actor_type=actor_type,
                    client=client,
                    occurred_at=created_at,
                    payload_json={},
                    created_at=created_at,
                )
            )

    def get_application(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(select(applications).where(applications.c.id == application_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def list_applications(self) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                select(applications).order_by(applications.c.created_at, applications.c.id)
            ).mappings()
            return [dict(row) for row in rows]

    def record_event(self, application_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = new_id()
        with self.transaction() as connection:
            connection.execute(
                insert(application_events).values(
                    id=event_id,
                    application_id=application_id,
                    event_type=event_type,
                    payload_json=payload,
                    created_at=utc_now(),
                )
            )
        return event_id

    def set_normalized_role(self, application_id: str, normalized_role: str) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                update(applications)
                .where(applications.c.id == application_id)
                .values(normalized_role=normalized_role, updated_at=utc_now())
            )
            if result.rowcount != 1:
                raise UnknownRecord(application_id)
