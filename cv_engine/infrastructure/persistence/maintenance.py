from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, func, select

from ...application.ports.transactions import ReadTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import artifact_versions


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

    def artifact_inventory(self, tx: ReadTransaction) -> list[dict[str, Any]]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    artifact_versions.c.id,
                    artifact_versions.c.path,
                    artifact_versions.c.content_hash,
                ).order_by(artifact_versions.c.created_at, artifact_versions.c.id)
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]
