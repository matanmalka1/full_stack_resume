"""Stateless token adapter for a user's Knowledge rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, exists, insert, select, update
from sqlalchemy.exc import IntegrityError

from ...application.errors import StateConflict
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...application.ports.user_knowledge import StoredKnowledge
from ...util import new_id
from .connection import SqlAlchemyTransactionManager
from .tables import candidate_contexts, fact_events, profile_bindings, users
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
#: What a mutation may write; `fact_id`, `source` and `ordinal` are a fact's identity.
_FACT_IDENTITY = ("fact_id", "source", "ordinal")
_FACT_CONTENT_COLUMNS = tuple(column for column in _FACT_COLUMNS if column not in _FACT_IDENTITY)
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

    def assign_unowned_fact_events(self, tx: WriteTransaction, user_id: str) -> int:
        cursor = self._transactions.connection_for(tx, access="write").execute(
            update(fact_events).where(fact_events.c.user_id.is_(None)).values(user_id=user_id)
        )
        return cursor.rowcount

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
        try:
            self._insert(connection, user_id, facts, candidate, bindings, imported_at)
        except IntegrityError as error:
            # A concurrent import got there first: past `has_knowledge`, the unique
            # keys are what make the import run once.
            if getattr(error.orig, "sqlstate", None) != "23505":
                raise
            raise StateConflict("This user already has Knowledge; import runs once.") from None

    @staticmethod
    def _insert(
        connection: Connection,
        user_id: str,
        facts: list[dict[str, Any]],
        candidate: dict[str, Any],
        bindings: dict[str, dict[str, Any]],
        imported_at: str,
    ) -> None:
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

    def sole_user_id(self, tx: ReadTransaction) -> str | None:
        # `users_single_user` admits at most one row until isolation is complete.
        return (
            self._transactions.connection_for(tx).execute(select(users.c.id)).scalar_one_or_none()
        )

    def knowledge_state(self, tx: ReadTransaction, user_id: str) -> StoredKnowledge | None:
        rows, candidate, bindings = self.stored_knowledge(tx, user_id)
        if candidate is None:
            return None
        connection = self._transactions.connection_for(tx)
        fact_store_version = connection.execute(
            select(candidate_contexts.c.fact_store_version).where(
                candidate_contexts.c.user_id == user_id
            )
        ).scalar_one()
        binding_versions = {
            row.profile_id: row.binding_version
            for row in connection.execute(
                select(profile_bindings.c.profile_id, profile_bindings.c.binding_version).where(
                    profile_bindings.c.user_id == user_id
                )
            )
        }
        return StoredKnowledge(
            user_id=user_id,
            facts=rows,
            candidate=candidate,
            bindings=bindings,
            fact_store_version=fact_store_version,
            binding_versions=binding_versions,
        )

    def insert_fact(
        self, tx: WriteTransaction, user_id: str, row: dict[str, Any], *, now: str
    ) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(facts_table).values(
                id=new_id(),
                user_id=user_id,
                **{column: row.get(column) for column in _FACT_COLUMNS},
                created_at=now,
                updated_at=now,
            )
        )

    def update_fact(
        self, tx: WriteTransaction, user_id: str, row: dict[str, Any], *, now: str
    ) -> None:
        cursor = self._transactions.connection_for(tx, access="write").execute(
            update(facts_table)
            .where(facts_table.c.user_id == user_id, facts_table.c.fact_id == row["fact_id"])
            .values(
                **{column: row.get(column) for column in _FACT_CONTENT_COLUMNS},
                updated_at=now,
            )
        )
        if cursor.rowcount != 1:
            raise StateConflict(f"fact {row['fact_id']} is not this user's")

    def set_binding(
        self,
        tx: WriteTransaction,
        user_id: str,
        profile_id: str,
        binding: dict[str, Any],
        *,
        expected_version: int,
        now: str,
    ) -> None:
        cursor = self._transactions.connection_for(tx, access="write").execute(
            update(profile_bindings)
            .where(
                profile_bindings.c.user_id == user_id,
                profile_bindings.c.profile_id == profile_id,
                profile_bindings.c.binding_version == expected_version,
            )
            .values(binding=binding, binding_version=expected_version + 1, updated_at=now)
        )
        if cursor.rowcount != 1:
            raise StateConflict(f"the {profile_id} binding changed while it was being written")

    def advance_fact_store_version(
        self, tx: WriteTransaction, user_id: str, *, expected: int, now: str
    ) -> int:
        cursor = self._transactions.connection_for(tx, access="write").execute(
            update(candidate_contexts)
            .where(
                candidate_contexts.c.user_id == user_id,
                candidate_contexts.c.fact_store_version == expected,
            )
            .values(fact_store_version=expected + 1, updated_at=now)
        )
        if cursor.rowcount != 1:
            # Two mutations read the same Knowledge; the later one is refused, not merged.
            raise StateConflict("Knowledge changed while it was being written; try again.")
        return expected + 1
