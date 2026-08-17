"""What an application command is asked for, and what it answers with.

The services used to return bare tuples, dicts, and paths, which meant every
caller re-derived the meaning of a position or a key. These types carry that
meaning once. They are deliberately thin: a command result names the records a
use-case produced, and nothing about how they are stored or displayed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.models import JobAnalysis, ValidationReport


@dataclass(frozen=True)
class IngestCommand:
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None


@dataclass(frozen=True)
class AnalyzeCommand:
    """`job_snapshot_id` is explicit: a command analyses one exact snapshot."""

    application_id: str
    job_snapshot_id: str
    track_override: str | None = None
    profile_override: str | None = None
    emphasis_override: str | None = None
    language_override: str | None = None
    accept_low_fit: bool = False
    use_ai: bool = False
    model: str | None = None


@dataclass(frozen=True)
class DraftCommand:
    """`job_analysis_id` is explicit: a draft is built from one exact analysis."""

    application_id: str
    job_analysis_id: str


@dataclass(frozen=True)
class IngestedApplication:
    application_id: str
    job_snapshot_id: str


@dataclass(frozen=True)
class AnalysisResult:
    analysis_id: str
    analysis: JobAnalysis


@dataclass(frozen=True)
class DraftResult:
    markdown: Path
    manifest: Path
    validation: ValidationReport


@dataclass(frozen=True)
class EditResult:
    markdown: Path
    validation: ValidationReport


@dataclass(frozen=True)
class ApprovalResult:
    version: int
    directory: Path
    decision_record_id: str


@dataclass(frozen=True)
class RenderResult:
    pdf: Path
    validation: ValidationReport


@dataclass(frozen=True)
class SubmissionResult:
    application_id: str
    pdf_artifact_version_id: str
    application: dict[str, Any]
