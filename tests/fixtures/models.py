from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cv_engine.application.commands import ApprovalResult
from cv_engine.domain.contracts.analysis import JobAnalysis
from cv_engine.domain.facts import FactStore
from cv_engine.runtime.composition import Services


@dataclass(frozen=True)
class WorkflowSetup:
    services: Services
    application_id: str
    snapshot_id: str
    analysis_id: str | None = None
    selection_plan_id: str | None = None
    markdown: Path | None = None
    manifest: Path | None = None
    draft_report: Any = None
    approved: ApprovalResult | None = None
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


@dataclass(frozen=True)
class ProposalSetup:
    services: Services
    application_id: str
    analysis_id: str
    analysis: JobAnalysis
    payload: dict[str, Any]
    operation_id: str = ""

    def __iter__(self):
        yield self.services
        yield self.application_id
        yield self.analysis
