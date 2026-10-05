from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cv_engine.application.commands import DocumentCheckResult
from cv_engine.domain.facts import FactStore
from cv_engine.runtime.composition import Services


@dataclass(frozen=True)
class WorkflowSetup:
    services: Services
    application_id: str
    job_text_hash: str
    analysis_id: str | None = None
    document_hash: str | None = None
    draft_report: Any = None
    approved: DocumentCheckResult | None = None
    pdf: Path | None = None
    ready_report: Any = None

    def __iter__(self):
        yield self.services
        yield self.application_id


@dataclass(frozen=True)
class DraftSetup:
    facts: FactStore
    profile: Any
    analysis: Any
    draft: Any
    markdown: Path | None
    candidate: Any = None

    def __iter__(self):
        yield self.facts
        yield self.profile
        yield self.analysis
        yield self.draft
        yield self.markdown
