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
    select,
)

from ...application.ports.transactions import ReadTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import ai_calls, users


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

    def user_ids(self, tx: ReadTransaction) -> list[str]:
        return list(
            self._transactions.connection_for(tx)
            .execute(select(users.c.id).order_by(users.c.id))
            .scalars()
        )

    def integrity_problems(self, tx: ReadTransaction) -> list[str]:
        return _integrity_problems(self._transactions.connection_for(tx))

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
