from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.records import ValidationRunLineage
from ...domain.contracts.validation import ValidationReport
from .transactions import ReadTransaction, WriteTransaction


class ValidationStore(Protocol):
    def record_validation(
        self,
        tx: WriteTransaction,
        application_id: str,
        phase: str,
        report: ValidationReport,
        artifact_version_id: str | None = None,
        *,
        lineage: ValidationRunLineage | None = None,
    ) -> str: ...

    def validation_lineage(
        self, tx: ReadTransaction, validation_id: str
    ) -> ValidationRunLineage: ...

    def latest_validation_for_working_draft(
        self, tx: ReadTransaction, working_draft_id: str
    ) -> dict[str, Any] | None: ...

    def validation_for_artifact(
        self, tx: ReadTransaction, application_id: str, phase: str, artifact_version_id: str
    ) -> ValidationReport: ...

    def validation_report(self, tx: ReadTransaction, validation_id: str) -> ValidationReport: ...

    def validation_run(self, tx: ReadTransaction, validation_id: str) -> dict[str, Any]: ...
