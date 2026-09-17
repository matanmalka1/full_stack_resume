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
        source_url: str | None,
        notes: str,
        source: str,
        created_at: str,
    ) -> None: ...

    def get_application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]: ...

    def update_application_notes(
        self,
        tx: WriteTransaction,
        application_id: str,
        notes: str,
        expected_notes: str,
        *,
        updated_at: str,
    ) -> dict[str, Any]: ...


class JobSnapshotStore(Protocol):
    def duplicate_application_inputs(self, tx: ReadTransaction) -> list[dict[str, Any]]: ...

    def snapshot_for_content_hash(
        self, tx: ReadTransaction, application_id: str, content_hash: str
    ) -> dict[str, Any] | None: ...

    def insert_initial_snapshot(
        self,
        tx: WriteTransaction,
        *,
        snapshot_id: str,
        application_id: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        source_metadata: dict[str, Any],
        captured_at: str,
    ) -> None: ...

    def insert_next_snapshot(
        self,
        tx: WriteTransaction,
        *,
        snapshot_id: str,
        application_id: str,
        payload_path: str,
        source_hash: str,
        normalized_hash: str,
        source_url: str | None,
        source_metadata: dict[str, Any],
        captured_at: str,
    ) -> None: ...


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
