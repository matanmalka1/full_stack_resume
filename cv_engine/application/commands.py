"""Typed command inputs and application-boundary outcomes.

These models are deliberately storage-neutral. A client receives identities,
validated domain documents, and workflow state; local paths are resolved only
by CLI compatibility code or an infrastructure adapter.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import Fact, JobAnalysis, ValidationReport


class BoundaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IngestCommand(BoundaryDTO):
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None


class AnalyzeCommand(BoundaryDTO):
    application_id: str
    job_snapshot_id: str
    track_override: str | None = None
    profile_override: str | None = None
    emphasis_override: str | None = None
    language_override: str | None = None
    accept_low_fit: bool = False
    provider: str = "deterministic"
    model: str = "rules-v1"


class DraftCommand(BoundaryDTO):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str


class RenderCommand(BoundaryDTO):
    application_id: str
    approved_revision_id: str


class RecruitmentStatusCommand(BoundaryDTO):
    application_id: str
    target_status: str
    reason: str = ""
    occurred_at: str | None = None
    actor_type: Literal["user", "system", "migration"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class RecruitmentCorrectionCommand(BoundaryDTO):
    application_id: str
    target_status: str
    corrects_event_id: str
    reason: str = Field(min_length=1)
    occurred_at: str | None = None
    actor_type: Literal["user", "system", "migration"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class SubmissionCommand(BoundaryDTO):
    application_id: str
    approved_revision_id: str
    pdf_artifact_version_id: str
    submitted_at: str = Field(min_length=1)
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system", "migration"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class ExternalSubmissionCommand(BoundaryDTO):
    application_id: str
    submitted_at: str = Field(min_length=1)
    artifact_version_id: str | None = None
    metadata: dict[str, Any] = {}
    actor_type: Literal["user", "system", "migration"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class NextActionCommand(BoundaryDTO):
    application_id: str
    next_action: str | None = None
    next_action_date: str | None = None
    occurred_at: str | None = None
    actor_type: Literal["user", "system", "migration"] = "user"
    client: Literal["web", "cli", "worker"] = "cli"


class IngestedApplication(BoundaryDTO):
    application_id: str
    job_snapshot_id: str


class AnalysisResult(BoundaryDTO):
    application_id: str
    job_snapshot_id: str
    analysis_id: str
    selection_plan_id: str
    analysis: JobAnalysis


class DraftResult(BoundaryDTO):
    application_id: str
    job_analysis_id: str
    selection_plan_id: str
    working_draft_id: str
    edit_version: int
    validation: ValidationReport


class EditResult(BoundaryDTO):
    application_id: str
    working_draft_id: str
    edit_version: int
    validation: ValidationReport


class ApprovalResult(BoundaryDTO):
    application_id: str
    revision_id: str
    version: int
    markdown_artifact_version_id: str
    manifest_artifact_version_id: str
    decision_record_id: str


class RenderResult(BoundaryDTO):
    application_id: str
    pdf_artifact_version_id: str
    validation: ValidationReport


class ApplicationMutationResult(BoundaryDTO):
    application_id: str
    current_status: str
    terminal_outcome: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    event_id: str | None = None


class SubmissionResult(ApplicationMutationResult):
    submission_id: str
    approved_revision_id: str | None = None
    pdf_artifact_version_id: str | None = None
    warnings: list[str] = []


class DecisionMarkdownExport(BoundaryDTO):
    application_id: str
    approved_revision_id: str
    filename: str
    content: str
    content_hash: str


class KnowledgeVersionsResult(BoundaryDTO):
    facts: str
    facts_lifecycle: str
    profiles: str
    emphasis_policies: str
    presentations: str
    candidate_context: str


class FactEventView(BoundaryDTO):
    id: str
    fact_id: str
    source_file: str
    event_type: str
    from_status: str | None
    to_status: str
    application_id: str | None
    claim_id: str | None
    reason: str
    fact_hash: str
    facts_version: str
    lifecycle_version: str
    created_at: str


class FactListItem(BoundaryDTO):
    fact: Fact
    recorded_status: str | None = None


class FactListResult(BoundaryDTO):
    items: list[FactListItem]


class FactDetailResult(BoundaryDTO):
    fact: Fact
    events: list[FactEventView]


class FactHistoryResult(BoundaryDTO):
    events: list[FactEventView]


class FactMutationResult(BoundaryDTO):
    fact: Fact
    event_id: str
    facts_version: str
    lifecycle_version: str


class FactAttachmentResult(FactMutationResult):
    profile: str
    section: str
    pinned: bool
    profile_source: str
    profile_store_version: str


class FactReconciliationResult(BoundaryDTO):
    passed: bool
    fact_counts: dict[str, int]
    tracked_facts: int
    facts_version: str
    lifecycle_version: str
    problems: list[str]


def fact_event_view(record: dict[str, Any]) -> FactEventView:
    """Strip persistence-only payload columns from one audit row."""
    return FactEventView.model_validate(
        {key: record.get(key) for key in FactEventView.model_fields}
    )
