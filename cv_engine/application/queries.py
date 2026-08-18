"""Purpose-built read projections returned by the application layer."""

from __future__ import annotations

import json
from typing import Any

from .commands import BoundaryDTO
from ..domain.models import JobAnalysis


class ApplicationView(BoundaryDTO):
    id: str
    company: str
    target_role: str
    normalized_role: str | None = None
    source_url: str | None = None
    language: str | None = None
    track: str | None = None
    profile: str | None = None
    emphasis: str | None = None
    classification_confidence: float | None = None
    fit_level: str | None = None
    current_status: str
    last_contact_date: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    notes: str = ""
    source: str = "manual"
    created_at: str
    updated_at: str


class JobSnapshotView(BoundaryDTO):
    id: str
    application_id: str
    version_number: int
    job_text: str
    source_url: str | None = None
    captured_at: str
    source_metadata: dict[str, Any]
    content_hash: str
    prior_snapshot_id: str | None = None


class JobAnalysisView(BoundaryDTO):
    id: str
    application_id: str
    job_snapshot_id: str
    version_number: int
    analysis: JobAnalysis
    provider: str
    model: str
    created_at: str


class ApplicationDetailView(BoundaryDTO):
    application: ApplicationView
    latest_snapshot: JobSnapshotView
    latest_analysis: JobAnalysisView | None = None


class ApplicationListView(BoundaryDTO):
    items: list[ApplicationView]


class ArtifactVersionView(BoundaryDTO):
    id: str
    artifact_id: str
    revision_id: str | None = None
    artifact_type: str
    logical_name: str
    version_number: int
    lifecycle_status: str
    content_hash: str
    created_at: str
    approved_at: str | None = None
    submitted_at: str | None = None
    track: str | None = None
    profile: str | None = None
    emphasis: str | None = None
    facts_version: str | None = None
    job_snapshot_id: str | None = None
    metadata: dict[str, Any]


class ArtifactVersionsView(BoundaryDTO):
    items: list[ArtifactVersionView]


class DecisionRecordView(BoundaryDTO):
    id: str
    application_id: str
    artifact_version_id: str | None = None
    job_snapshot_id: str
    job_analysis_id: str
    structured: dict[str, Any]
    summary: str
    created_at: str


def application_view(record: dict[str, Any]) -> ApplicationView:
    return ApplicationView.model_validate(record)


def snapshot_view(record: dict[str, Any], job_text: str) -> JobSnapshotView:
    return JobSnapshotView.model_validate(
        {
            **{
                key: record.get(key)
                for key in JobSnapshotView.model_fields
                if key not in {"source_metadata", "job_text"}
            },
            "job_text": job_text,
            "source_metadata": json.loads(record.get("source_metadata_json") or "{}"),
        }
    )


def analysis_view(record: dict[str, Any]) -> JobAnalysisView:
    return JobAnalysisView.model_validate(
        {
            **{key: record.get(key) for key in JobAnalysisView.model_fields if key != "analysis"},
            "analysis": record["analysis"],
        }
    )


def artifact_version_view(record: dict[str, Any]) -> ArtifactVersionView:
    return ArtifactVersionView.model_validate(
        {
            **{
                key: record.get(key)
                for key in ArtifactVersionView.model_fields
                if key != "metadata"
            },
            "metadata": json.loads(record.get("metadata_json") or "{}"),
        }
    )


def decision_view(record: dict[str, Any]) -> DecisionRecordView:
    return DecisionRecordView.model_validate(
        {
            **{
                key: record.get(key)
                for key in DecisionRecordView.model_fields
                if key != "structured"
            },
            "structured": json.loads(record.get("structured_json") or "{}"),
        }
    )
