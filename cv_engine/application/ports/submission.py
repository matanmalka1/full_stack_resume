from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.records import ApprovedRevision
from .transactions import ReadTransaction


@dataclass(frozen=True)
class SubmissionContext:
    application: dict
    revision: ApprovedRevision | None
    latest_snapshot_id: str | None
    latest_analysis_id: str | None
    latest_selection_plan_id: str | None


class SubmissionContextReader(Protocol):
    def load(
        self, tx: ReadTransaction, application_id: str, revision_id: str | None
    ) -> SubmissionContext: ...
