from __future__ import annotations

from typing import Any

from sqlalchemy import exists, insert, select, update

from ...application.errors import StateConflict, UnknownRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import applications, submissions


class SqlAlchemyApplicationStore:
    """Application identity and mutable intake fields; no transaction ownership."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_application(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        company: str,
        target_role: str,
        notes: str,
        job_text: str,
        job_text_hash: str,
        job_normalized_hash: str,
        source_url: str | None,
        created_at: str,
    ) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(applications).values(
                id=application_id,
                company=company.strip(),
                target_role=target_role.strip(),
                current_status="saved",
                notes=notes,
                job_text=job_text,
                job_text_hash=job_text_hash,
                job_normalized_hash=job_normalized_hash,
                source_url=source_url,
                job_text_updated_at=created_at,
                created_at=created_at,
                updated_at=created_at,
            )
        )

    def get_application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def duplicate_application_inputs(self, tx: ReadTransaction) -> list[dict[str, Any]]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(
                    applications.c.id.label("application_id"),
                    applications.c.company,
                    applications.c.target_role,
                    applications.c.source_url,
                    applications.c.job_normalized_hash.label("normalized_hash"),
                )
                .where(applications.c.deleted_at.is_(None))
                .order_by(applications.c.created_at, applications.c.id)
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def update_job_text(
        self,
        tx: WriteTransaction,
        application_id: str,
        *,
        job_text: str,
        job_text_hash: str,
        job_normalized_hash: str,
        source_url: str | None,
        expected_job_text_hash: str,
        updated_at: str,
    ) -> dict[str, Any]:
        """Replace the job text the client last read, unless a Submission locked it.

        The row lock orders this against `submit_application`, which locks the same
        row before it records what was sent; the trigger `lock_submitted_job_text`
        refuses the same change in the database.
        """
        connection = self._transactions.connection_for(tx, access="write")
        current = (
            connection.execute(
                select(applications.c.job_text_hash)
                .where(applications.c.id == application_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise UnknownRecord(application_id)
        if current["job_text_hash"] != expected_job_text_hash:
            raise StateConflict("the job text changed since it was read (expected_job_text_hash)")
        if connection.execute(
            select(exists().where(submissions.c.application_id == application_id))
        ).scalar_one():
            raise StateConflict("the job text is locked: the application has a submission")
        connection.execute(
            update(applications)
            .where(applications.c.id == application_id)
            .values(
                job_text=job_text,
                job_text_hash=job_text_hash,
                job_normalized_hash=job_normalized_hash,
                source_url=source_url,
                job_text_updated_at=updated_at,
                updated_at=updated_at,
            )
        )
        row = (
            connection.execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one()
        )
        return dict(row)

    def update_application_notes(
        self,
        tx: WriteTransaction,
        application_id: str,
        notes: str,
        expected_notes: str,
        *,
        updated_at: str,
    ) -> dict[str, Any]:
        connection = self._transactions.connection_for(tx, access="write")
        result = connection.execute(
            update(applications)
            .where(
                applications.c.id == application_id,
                applications.c.notes == expected_notes,
            )
            .values(notes=notes, updated_at=updated_at)
        )
        if result.rowcount != 1:
            exists_row = connection.execute(
                select(applications.c.id).where(applications.c.id == application_id)
            ).scalar_one_or_none()
            if exists_row is None:
                raise UnknownRecord(application_id)
            raise StateConflict("application notes changed before commit")
        row = (
            connection.execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one()
        )
        return dict(row)
