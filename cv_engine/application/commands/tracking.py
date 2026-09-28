"""Recruitment-pipeline commands and results: status, next action, submission."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ._base import BoundaryDTO, WriteClient


class CloseApplicationCommand(BoundaryDTO):
    application_id: str
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class DeleteApplicationCommand(BoundaryDTO):
    application_id: str
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class RecruitmentStatusCommand(BoundaryDTO):
    application_id: str
    target_status: str
    reason: str = ""
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class RecruitmentCorrectionCommand(BoundaryDTO):
    application_id: str
    target_status: str
    corrects_event_id: str
    reason: str = Field(min_length=1)
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class SubmissionCommand(BoundaryDTO):
    """§18: record that the Ready document the client was showing was sent."""

    application_id: str
    expected_document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class ExternalSubmissionCommand(BoundaryDTO):
    application_id: str
    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class NextActionCommand(BoundaryDTO):
    application_id: str
    next_action: str | None = None
    next_action_date: str | None = None
    occurred_at: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class ApplicationMutationResult(BoundaryDTO):
    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None


class SubmissionResult(ApplicationMutationResult):
    submission_id: str
    document_hash: str | None = None
    warnings: list[str] = []
