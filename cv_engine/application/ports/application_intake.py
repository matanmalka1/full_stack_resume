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
        company: str,
        target_role: str,
        notes: str,
        job_text: str,
        job_text_hash: str,
        job_normalized_hash: str,
        source_url: str | None,
        created_at: str,
    ) -> None: ...

    def get_application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]: ...

    def duplicate_application_inputs(self, tx: ReadTransaction) -> list[dict[str, Any]]: ...

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
    ) -> dict[str, Any]: ...

    def update_application_notes(
        self,
        tx: WriteTransaction,
        application_id: str,
        notes: str,
        expected_notes: str,
        *,
        updated_at: str,
    ) -> dict[str, Any]: ...


class InitialRecruitmentEventWriter(Protocol):
    def insert_initial_saved_event(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        actor_type: str,
        client: str,
        occurred_at: str,
    ) -> str: ...


class AuditLogWriter(Protocol):
    def insert_audit(self, tx: WriteTransaction, record: AuditRecord) -> None: ...
