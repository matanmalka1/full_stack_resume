"""Recruitment-pipeline composed repository view.

Extends `ReadinessRepository` (prep) intentionally: submission requires the
full Ready proof before a recruitment submission can be recorded.
"""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.records import AuditRecord
from .composed_prep import ReadinessRepository


class TrackingRepository(ReadinessRepository, Protocol):
    """Recruitment mutations plus the full Ready proof required by submission."""

    def insert_submission(
        self,
        submission_id: str,
        application_id: str,
        submission_type: str,
        approved_revision_id: str | None,
        artifact_version_id: str | None,
        submitted_at: str,
        metadata: dict[str, Any],
    ) -> None: ...

    def insert_recruitment_event(
        self,
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

    def insert_next_action_event(
        self,
        *,
        application_id: str,
        next_action: str | None,
        next_action_date: str | None,
        actor_type: str,
        client: str,
        occurred_at: str,
    ) -> str: ...

    def recruitment_event(self, event_id: str) -> dict[str, Any]: ...

    def recruitment_events(self, application_id: str) -> list[dict[str, Any]]: ...

    def submissions(self, application_id: str) -> list[dict[str, Any]]: ...

    def insert_audit(self, record: AuditRecord) -> None: ...

    def audit_records(self, application_id: str) -> list[dict[str, Any]]: ...
