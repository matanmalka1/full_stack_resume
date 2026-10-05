from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    func,
    literal,
    select,
    union,
)

from ...application.ports.transactions import ReadTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import ai_calls, submissions


def _integrity_problems(connection) -> list[str]:
    catalog = MetaData()
    constraints = Table(
        "pg_constraint",
        catalog,
        Column("conname", String),
        Column("connamespace", Integer),
        Column("contype", String),
        Column("convalidated", Boolean),
        schema="pg_catalog",
    )
    namespaces = Table(
        "pg_namespace",
        catalog,
        Column("oid", Integer),
        Column("nspname", String),
        schema="pg_catalog",
    )
    names = connection.execute(
        select(constraints.c.conname)
        .select_from(constraints.join(namespaces, namespaces.c.oid == constraints.c.connamespace))
        .where(
            constraints.c.contype == "f",
            constraints.c.convalidated.is_(False),
            namespaces.c.nspname == func.current_schema(),
        )
        .order_by(constraints.c.conname)
    ).scalars()
    return [f"foreign key constraint not validated: {name}" for name in names]


class SqlAlchemyMaintenanceInspection:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def integrity_problems(self, tx: ReadTransaction) -> list[str]:
        return _integrity_problems(self._transactions.connection_for(tx))

    def registered_payloads(self, tx: ReadTransaction) -> list[dict[str, Any]]:
        """Every registered immutable file and the hash it was registered with.

        Every Submission file (§19b). The document's rendered files are mutable
        working outputs and are not listed.
        """
        connection = self._transactions.connection_for(tx)
        submitted = (
            connection.execute(
                union(
                    select(
                        submissions.c.id,
                        submissions.c.html_path.label("path"),
                        submissions.c.html_sha256.label("content_hash"),
                        submissions.c.submitted_at,
                        literal(0).label("position"),
                    ).where(submissions.c.submission_type == "internal"),
                    select(
                        submissions.c.id,
                        submissions.c.pdf_path.label("path"),
                        submissions.c.pdf_sha256.label("content_hash"),
                        submissions.c.submitted_at,
                        literal(1).label("position"),
                    ).where(submissions.c.submission_type == "internal"),
                ).order_by("submitted_at", "id", "position")
            )
            .mappings()
            .all()
        )
        return [
            {"id": row["id"], "path": row["path"], "content_hash": row["content_hash"]}
            for row in submitted
        ]

    def registered_payload_references(self, tx: ReadTransaction) -> set[str]:
        statement = union(
            select(submissions.c.html_path).where(submissions.c.html_path.is_not(None)),
            select(submissions.c.pdf_path).where(submissions.c.pdf_path.is_not(None)),
        )
        return set(self._transactions.connection_for(tx).execute(statement).scalars())

    def ai_call_evidence(self, tx: ReadTransaction) -> list[dict[str, Any]]:
        """Every logged call that kept a response, with the hash it was logged under."""
        return [
            dict(row)
            for row in self._transactions.connection_for(tx)
            .execute(
                select(
                    ai_calls.c.id,
                    ai_calls.c.sanitized_response,
                    ai_calls.c.sanitized_response_hash,
                )
                .where(ai_calls.c.sanitized_response.is_not(None))
                .order_by(ai_calls.c.started_at, ai_calls.c.id)
            )
            .mappings()
        ]
