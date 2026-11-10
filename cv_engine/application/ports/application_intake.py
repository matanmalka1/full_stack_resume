"""Narrow persistence capabilities consumed by Application Intake."""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.records import AuditRecord
from .transactions import ReadTransaction, WriteTransaction


class IntakeApplicationStore(Protocol):
    def insert_application(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        user_id: str,
        company: str,
        target_role: str,
        notes: str,
        job_text: str,
        job_text_hash: str,
        job_normalized_hash: str,
        source_url: str | None,
        created_at: str,
    ) -> None: ...

    def get_application(
        self, tx: ReadTransaction, application_id: str, user_id: str
    ) -> dict[str, Any]:
        """The user's Application; `UnknownRecord` for another user's, as for a missing one."""
        ...

    def duplicate_application_inputs(
        self, tx: ReadTransaction, user_id: str
    ) -> list[dict[str, Any]]: ...

    def update_job_text(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        *,
        job_text: str,
        job_text_hash: str,
        job_normalized_hash: str,
        source_url: str | None,
        expected_job_text_hash: str,
        updated_at: str,
    ) -> dict[str, Any]: ...

    def set_deleted(
        self, tx: WriteTransaction, application_id: str, user_id: str, deleted_at: str
    ) -> None:
        """Soft-delete the user's active Application; `StateConflict` if already deleted."""
        ...

    def update_application_notes(
        self,
        tx: WriteTransaction,
        application_id: str,
        user_id: str,
        notes: str,
        expected_notes: str,
        *,
        updated_at: str,
    ) -> dict[str, Any]: ...


class AuditLogWriter(Protocol):
    def insert_audit(self, tx: WriteTransaction, record: AuditRecord) -> None: ...
