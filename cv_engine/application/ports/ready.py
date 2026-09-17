from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...domain.contracts.records import ApprovedRevision, ValidationRunLineage
from ...domain.contracts.selection import SelectionPlan
from ...domain.contracts.validation import ValidationReport
from .transactions import ReadTransaction


@dataclass(frozen=True)
class ReadyEvidence:
    revision: ApprovedRevision
    source_artifacts: dict[str, dict[str, Any]]
    rendered_artifacts: dict[str, dict[str, Any]]
    selected_pdf: dict[str, Any] | None
    analysis: dict[str, Any] | None
    plan: SelectionPlan | None
    decision: dict[str, Any] | None
    approval_validation: ValidationReport | None
    approval_lineage: ValidationRunLineage | None
    post_render_validation: ValidationReport | None
    integrity_problems: tuple[str, ...]


class ReadyEvidenceReader(Protocol):
    def load(
        self,
        tx: ReadTransaction,
        application_id: str,
        revision_id: str | None = None,
        pdf_artifact_version_id: str | None = None,
    ) -> ReadyEvidence: ...
