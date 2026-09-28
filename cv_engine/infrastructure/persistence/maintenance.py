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
from .tables import artifact_versions, job_snapshots, submissions


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
        """Every registered immutable file and the hash it was registered with.

        JobSnapshot payloads, provider-response artifact versions and every Submission
        file (§19b). The document's rendered files are mutable working outputs and are
        not listed.
        """
        connection = self._transactions.connection_for(tx)
        snapshots = (
            connection.execute(
                select(
                    job_snapshots.c.id,
                    job_snapshots.c.payload_path.label("path"),
                    job_snapshots.c.source_hash.label("content_hash"),
                ).order_by(job_snapshots.c.captured_at, job_snapshots.c.id)
            )
            .mappings()
            .all()
        )
        artifacts = (
            connection.execute(
                select(
                    artifact_versions.c.id,
                    artifact_versions.c.path,
                    artifact_versions.c.content_hash,
                ).order_by(artifact_versions.c.created_at, artifact_versions.c.id)
            )
            .mappings()
            .all()
        )
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
        return [dict(row) for row in (*snapshots, *artifacts)] + [
            {"id": row["id"], "path": row["path"], "content_hash": row["content_hash"]}
            for row in submitted
        ]

    def registered_payload_references(self, tx: ReadTransaction) -> set[str]:
        statement = union(
            select(job_snapshots.c.payload_path),
            select(artifact_versions.c.path),
            select(submissions.c.html_path).where(submissions.c.html_path.is_not(None)),
            select(submissions.c.pdf_path).where(submissions.c.pdf_path.is_not(None)),
        )
        return set(self._transactions.connection_for(tx).execute(statement).scalars())
