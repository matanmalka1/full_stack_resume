"""Analysis lifecycle and consumer-specific source contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.analysis import JobAnalysis
from ...domain.knowledge import Knowledge
from .transactions import ReadTransaction, WriteTransaction


@dataclass(frozen=True)
class AnalysisSnapshotSource:
    application_id: str
    job_snapshot_id: str
    payload_path: str
    source_hash: str
    normalized_hash: str
    active_snapshot_id: str
    deleted_at: str | None


@dataclass(frozen=True)
class AnalysisContextSource:
    application_id: str
    job_analysis_id: str
    job_snapshot_id: str
    analysis: JobAnalysis
    active_analysis_id: str | None
    active_snapshot_id: str
    deleted_at: str | None


class AnalysisPayloadStore(Protocol):
    """Only verified JobSnapshot reads."""

    def read_snapshot(self, reference: str, expected_hash: str) -> str: ...


class AnalysisKnowledgeSource(Protocol):
    """Read canonical files only; the caller checks recovery state through its token."""

    def load(self) -> Knowledge: ...


class AnalysisContextSourceReader(Protocol):
    def knowledge_is_prepared(self, tx: ReadTransaction) -> bool: ...

    def analysis_source(
        self, tx: ReadTransaction, job_snapshot_id: str
    ) -> AnalysisSnapshotSource: ...

    def analysis_context_source(
        self, tx: ReadTransaction, job_analysis_id: str
    ) -> AnalysisContextSource: ...


class AnalysisStore(Protocol):
    """Analysis writes and the Application's current matching configuration."""

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None: ...

    def save_analysis(
        self,
        tx: WriteTransaction,
        application_id: str,
        snapshot_id: str,
        analysis: JobAnalysis,
        *,
        provider: str,
        model: str,
        expected_analysis_id: str | None = None,
        refuse_matching_context_operation: bool = False,
    ) -> str: ...

    def refuse_matching_context_operation(
        self, tx: WriteTransaction, application_id: str
    ) -> None: ...

    def set_normalized_role(
        self, tx: WriteTransaction, application_id: str, normalized_role: str
    ) -> None: ...
