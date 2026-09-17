from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...application.errors import UnknownRecord
from .base import SqlAlchemyRepositoryBase, json_text_record
from .tables import recruitment_events, submissions

_RECRUITMENT_EVENT_COLUMNS = tuple(
    column for column in recruitment_events.c if column.name != "seq"
)
_SUBMISSION_COLUMNS = tuple(column for column in submissions.c if column.name != "seq")


class SqlAlchemyTrackingProjection(SqlAlchemyRepositoryBase):
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
        return json_text_record(row, "payload_json")

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
        return [json_text_record(row, "payload_json") for row in rows]

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
        return [json_text_record(row, "metadata_json") for row in rows]
