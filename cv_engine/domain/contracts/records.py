"""Immutable approval, decision, audit, and validation-lineage records."""

from __future__ import annotations

from typing import Any, Literal

from .base import StrictModel


class ApprovedRevision(StrictModel):
    """One immutable approved resume and its complete frozen lineage.

    Payload references are opaque project-relative identities. The domain
    record neither composes nor opens them; infrastructure owns that policy.
    """

    id: str
    application_id: str
    version_number: int
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    working_draft_id: str
    draft_edit_version: int
    draft_content_hash: str
    resume_json_reference: str
    resume_json_hash: str
    resume_markdown_reference: str
    resume_markdown_hash: str
    candidate_context_version: str
    candidate_context_hash: str
    facts_version: str
    knowledge_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    validation_run_id: str
    validator_versions: dict[str, str]
    decision_provenance: dict[str, str]
    approved_at: str


class DecisionRecord(StrictModel):
    """The immutable approval decision stored beside an approved artifact."""

    id: str
    application_id: str
    artifact_version_id: str
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str


class AuditRecord(StrictModel):
    """One immutable local actor record for an application-layer decision."""

    id: str
    application_id: str
    action: str
    entity_type: str
    entity_id: str
    actor_type: Literal["user", "system"]
    client: Literal["web", "worker"]
    occurred_at: str
    details: dict[str, Any] = {}


class ValidationRunLineage(StrictModel):
    """Exact mutable-draft and frozen-context inputs validated by one run."""

    working_draft_id: str
    edit_version: int
    content_hash: str
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    knowledge_context_hash: str
    validator_versions: dict[str, str]
