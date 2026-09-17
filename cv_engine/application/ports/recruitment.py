from __future__ import annotations

from typing import Any, Protocol

from .transactions import ReadTransaction, WriteTransaction


class RecruitmentStore(Protocol):
    def application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]: ...

    def set_deleted(self, tx: WriteTransaction, application_id: str, deleted_at: str) -> None: ...

    def event(self, tx: ReadTransaction, event_id: str) -> dict[str, Any]: ...

    def insert_event(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        expected_current_status: str,
        target_status: str,
        event_type: str,
        reason: str,
        actor_type: str,
        client: str,
        occurred_at: str,
        terminal_outcome: str | None,
        corrects_event_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str: ...

    def insert_next_action(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        next_action: str | None,
        next_action_date: str | None,
        actor_type: str,
        client: str,
        occurred_at: str,
    ) -> str: ...

    def insert_submission(
        self,
        tx: WriteTransaction,
        submission_id: str,
        application_id: str,
        submission_type: str,
        approved_revision_id: str | None,
        artifact_version_id: str | None,
        submitted_at: str,
        metadata: dict[str, Any],
    ) -> None: ...
