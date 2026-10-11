"""Stateless token adapter for a user's Knowledge rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import exists, insert, select

from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import new_id
from .connection import SqlAlchemyTransactionManager
from .tables import candidate_contexts, profile_bindings
from .tables import facts as facts_table

_FACT_COLUMNS = (
    "fact_id",
    "status",
    "source",
    "ordinal",
    "meaning",
    "renderings",
    "tags",
    "provenance",
    "effective_dates",
    "resume_style",
    "link_target",
    "replaces",
    "confirmed_at",
)
_CANDIDATE_COLUMNS = (
    "context_version",
    "name_fact_id",
    "filename_name",
    "filename_language",
    "locale",
    "timezone",
    "contact_fact_ids",
    "track_contact_fact_ids",
    "link_schemes",
)


class SqlAlchemyUserKnowledgeRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def has_knowledge(self, tx: ReadTransaction, user_id: str) -> bool:
        connection = self._transactions.connection_for(tx)
        return any(
            connection.execute(select(exists().where(table.c.user_id == user_id))).scalar_one()
            for table in (facts_table, candidate_contexts, profile_bindings)
        )

    def insert_knowledge(
        self,
        tx: WriteTransaction,
        user_id: str,
        *,
        facts: list[dict[str, Any]],
        candidate: dict[str, Any],
        bindings: dict[str, dict[str, Any]],
        imported_at: str,
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        if facts:
            connection.execute(
                insert(facts_table),
                [
                    {
                        "id": new_id(),
                        "user_id": user_id,
                        **{column: row.get(column) for column in _FACT_COLUMNS},
                        "created_at": imported_at,
                        "updated_at": imported_at,
                    }
                    for row in facts
                ],
            )
        connection.execute(
            insert(candidate_contexts).values(
                user_id=user_id,
                **{column: candidate.get(column) for column in _CANDIDATE_COLUMNS},
                fact_store_version=0,
                updated_at=imported_at,
            )
        )
        if bindings:
            connection.execute(
                insert(profile_bindings),
                [
                    {
                        "user_id": user_id,
                        "profile_id": profile_id,
                        "binding": binding,
                        "binding_version": 1,
                        "updated_at": imported_at,
                    }
                    for profile_id, binding in bindings.items()
                ],
            )

    def stored_knowledge(
        self, tx: ReadTransaction, user_id: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, dict[str, Any]]]:
        connection = self._transactions.connection_for(tx)
        fact_rows = [
            {column: row[column] for column in _FACT_COLUMNS}
            for row in connection.execute(
                select(facts_table)
                .where(facts_table.c.user_id == user_id)
                .order_by(facts_table.c.source, facts_table.c.ordinal)
            ).mappings()
        ]
        candidate_row = (
            connection.execute(
                select(candidate_contexts).where(candidate_contexts.c.user_id == user_id)
            )
            .mappings()
            .one_or_none()
        )
        candidate = (
            None
            if candidate_row is None
            else {column: candidate_row[column] for column in _CANDIDATE_COLUMNS}
        )
        bindings = {
            row["profile_id"]: row["binding"]
            for row in connection.execute(
                select(profile_bindings).where(profile_bindings.c.user_id == user_id)
            ).mappings()
        }
        return fact_rows, candidate, bindings
