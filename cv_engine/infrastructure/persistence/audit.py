from __future__ import annotations

from typing import Any

from ...util import canonical_json, sha256_text, utc_now
from .base import SqliteRepositoryBase
from .primitives import new_id


class SqliteAuditRepository(SqliteRepositoryBase):
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
    ) -> str:
        event_id = new_id()
        payload = canonical_json(fact)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO fact_events(id, fact_id, source_file, event_type, from_status, "
                "to_status, application_id, claim_id, reason, fact_json, fact_hash, "
                "facts_version, lifecycle_version, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    fact_id,
                    source_file,
                    event_type,
                    from_status,
                    to_status,
                    application_id,
                    claim_id,
                    reason,
                    payload,
                    sha256_text(payload),
                    facts_version,
                    lifecycle_version,
                    utc_now(),
                ),
            )
        return event_id

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
