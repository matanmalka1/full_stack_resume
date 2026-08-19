from __future__ import annotations

from typing import Any

from ...domain.models import AuditRecord
from ...util import canonical_json, new_id, sha256_text, utc_now
from .base import SqliteRepositoryBase


class SqliteAuditRepository(SqliteRepositoryBase):
    def insert_audit(self, record: AuditRecord) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO audit_records(id, application_id, action, entity_type, entity_id, "
                "actor_type, client, installation_id, occurred_at, details_json) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.application_id,
                    record.action,
                    record.entity_type,
                    record.entity_id,
                    record.actor_type,
                    record.client,
                    record.installation_id,
                    record.occurred_at,
                    canonical_json(record.details),
                ),
            )

    def audit_records(self, application_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_records WHERE application_id=? ORDER BY occurred_at, rowid",
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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
            "fact_json": payload,
            "fact_hash": sha256_text(payload),
            "facts_version": facts_version,
            "lifecycle_version": lifecycle_version,
            "created_at": created_at or utc_now(),
        }
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM fact_events WHERE id=?", (event_id,)
            ).fetchone()
            if existing is not None:
                if dict(existing) != values:
                    raise ValueError("fact event identity already has different content")
                return event_id
            connection.execute(
                "INSERT INTO fact_events(id, fact_id, source_file, event_type, from_status, "
                "to_status, application_id, claim_id, reason, fact_json, fact_hash, "
                "facts_version, lifecycle_version, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    values["id"],
                    values["fact_id"],
                    values["source_file"],
                    values["event_type"],
                    values["from_status"],
                    values["to_status"],
                    values["application_id"],
                    values["claim_id"],
                    values["reason"],
                    values["fact_json"],
                    values["fact_hash"],
                    values["facts_version"],
                    values["lifecycle_version"],
                    values["created_at"],
                ),
            )
        return event_id

    def fact_event(self, event_id: str) -> dict[str, Any] | None:
        with self.read_connection() as connection:
            row = connection.execute("SELECT * FROM fact_events WHERE id=?", (event_id,)).fetchone()
        return None if row is None else dict(row)

    def fact_events(self, fact_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM fact_events"
        parameters: tuple[Any, ...] = ()
        if fact_id is not None:
            query += " WHERE fact_id=?"
            parameters = (fact_id,)
        query += " ORDER BY created_at, rowid"
        with self.read_connection() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def latest_fact_statuses(self) -> dict[str, str]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT fact_id, to_status FROM fact_events "
                "WHERE event_type IN ('fact_created', 'fact_promoted') "
                "ORDER BY created_at, rowid"
            ).fetchall()
        return {row["fact_id"]: row["to_status"] for row in rows}
