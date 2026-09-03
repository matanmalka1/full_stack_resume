from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select

from ...application.errors import StateConflict
from ...domain.contracts.records import AuditRecord
from ...util import canonical_json, new_id, sha256_text, utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import audit_records, fact_events


def _json_text_record(row: Any, field: str) -> dict[str, Any]:
    record = dict(row)
    record[field] = canonical_json(record[field])
    return record


class SqlAlchemyAuditRepository(SqlAlchemyRepositoryBase):
    def insert_audit(self, record: AuditRecord) -> None:
        with self.transaction() as connection:
            connection.execute(
                insert(audit_records).values(
                    id=record.id,
                    application_id=record.application_id,
                    action=record.action,
                    entity_type=record.entity_type,
                    entity_id=record.entity_id,
                    actor_type=record.actor_type,
                    client=record.client,
                    occurred_at=record.occurred_at,
                    details_json=record.details,
                )
            )

    def audit_records(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            visible_columns = [column for column in audit_records.c if column.name != "seq"]
            rows = (
                connection.execute(
                    select(*visible_columns)
                    .where(audit_records.c.application_id == application_id)
                    .order_by(audit_records.c.occurred_at, audit_records.c.seq)
                )
                .mappings()
                .all()
            )
        return [_json_text_record(row, "details_json") for row in rows]

    def record_fact_event(
        self,
        *,
        fact_id: str,
        source_file: str,
        event_type: str,
        from_status: str | None,
        to_status: str,
        fact: dict[str, Any],
        facts_version: str,
        lifecycle_version: str,
        reason: str = "",
        application_id: str | None = None,
        claim_id: str | None = None,
        event_id: str | None = None,
        created_at: str | None = None,
    ) -> str:
        event_id = event_id or new_id()
        payload = canonical_json(fact)
        values = {
            "id": event_id,
            "fact_id": fact_id,
            "source_file": source_file,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "application_id": application_id,
            "claim_id": claim_id,
            "reason": reason,
            "fact_json": fact,
            "fact_hash": sha256_text(payload),
            "facts_version": facts_version,
            "lifecycle_version": lifecycle_version,
            "created_at": created_at or utc_now(),
        }
        with self.transaction() as connection:
            visible_columns = [column for column in fact_events.c if column.name != "seq"]
            existing = (
                connection.execute(select(*visible_columns).where(fact_events.c.id == event_id))
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if dict(existing) != values:
                    raise StateConflict("fact event identity already has different content")
                return event_id
            connection.execute(insert(fact_events).values(**values))
        return event_id

    def fact_event(self, event_id: str) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            visible_columns = [column for column in fact_events.c if column.name != "seq"]
            row = (
                connection.execute(select(*visible_columns).where(fact_events.c.id == event_id))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _json_text_record(row, "fact_json")

    def fact_events(self, fact_id: str | None = None) -> list[dict[str, Any]]:
        visible_columns = [column for column in fact_events.c if column.name != "seq"]
        statement = select(*visible_columns)
        if fact_id is not None:
            statement = statement.where(fact_events.c.fact_id == fact_id)
        statement = statement.order_by(fact_events.c.created_at, fact_events.c.seq)
        with self.read_connection() as connection:
            return [
                _json_text_record(row, "fact_json")
                for row in connection.execute(statement).mappings()
            ]

    def latest_fact_statuses(self) -> dict[str, str]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(fact_events.c.fact_id, fact_events.c.to_status)
                    .where(fact_events.c.event_type.in_(("fact_created", "fact_promoted")))
                    .order_by(fact_events.c.created_at, fact_events.c.seq)
                )
                .mappings()
                .all()
            )
        return {row["fact_id"]: row["to_status"] for row in rows}
