"""Stateless transaction-token persistence for the Knowledge lifecycle."""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select

from ...application.errors import StateConflict, UnknownRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import canonical_json, new_id, sha256_text, utc_now
from .analysis_sql import _analysis_record
from .connection import SqlAlchemyTransactionManager
from .tables import fact_events, job_analyses


class SqlAlchemyKnowledgeLifecycleRepository:
    """Own fact events behind explicit transaction tokens."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def record_fact_event(self, tx: WriteTransaction, **event: Any) -> str:
        connection = self._transactions.connection_for(tx, access="write")
        event_id = event.get("event_id") or new_id()
        values = {
            "id": event_id,
            "fact_id": event["fact_id"],
            "source_file": event["source_file"],
            "event_type": event["event_type"],
            "from_status": event["from_status"],
            "to_status": event["to_status"],
            "application_id": event.get("application_id"),
            "claim_id": event.get("claim_id"),
            "reason": event.get("reason", ""),
            "fact_json": event["fact"],
            "fact_hash": sha256_text(canonical_json(event["fact"])),
            "facts_version": event["facts_version"],
            "lifecycle_version": event["lifecycle_version"],
            "created_at": event.get("created_at") or utc_now(),
            "user_id": event["user_id"],
        }
        visible = [column for column in fact_events.c if column.name != "seq"]
        existing = (
            connection.execute(select(*visible).where(fact_events.c.id == event_id))
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if dict(existing) != values:
                raise StateConflict("fact event identity already has different content")
            return event_id
        connection.execute(insert(fact_events).values(**values))
        return event_id

    @staticmethod
    def _event_record(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["fact_json"] = canonical_json(record["fact_json"])
        return record

    def fact_events(
        self, tx: ReadTransaction, user_id: str, fact_id: str | None = None
    ) -> list[dict[str, Any]]:
        visible = [column for column in fact_events.c if column.name != "seq"]
        statement = select(*visible).where(fact_events.c.user_id == user_id)
        if fact_id is not None:
            statement = statement.where(fact_events.c.fact_id == fact_id)
        rows = self._transactions.connection_for(tx).execute(
            statement.order_by(fact_events.c.created_at, fact_events.c.seq)
        )
        return [self._event_record(row) for row in rows.mappings()]

    def latest_fact_statuses(self, tx: ReadTransaction, user_id: str) -> dict[str, str]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(fact_events.c.fact_id, fact_events.c.to_status)
                .where(
                    fact_events.c.user_id == user_id,
                    fact_events.c.event_type.in_(
                        ("fact_created", "fact_confirmed", "fact_deleted")
                    ),
                )
                .order_by(fact_events.c.created_at, fact_events.c.seq)
            )
            .mappings()
            .all()
        )
        return {row["fact_id"]: row["to_status"] for row in rows}

    def get_analysis(
        self, tx: ReadTransaction, analysis_id: str, application_id: str
    ) -> dict[str, Any]:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(job_analyses).where(
                    job_analyses.c.id == analysis_id,
                    job_analyses.c.application_id == application_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return _analysis_record(row)
