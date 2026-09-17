"""Analysis/selection lifecycle and consumer-specific source contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.selection import SelectionManifest, SelectionPlan
from ...domain.contracts.taxonomy import Emphasis
from ...domain.knowledge import Knowledge
from .transactions import ReadTransaction, WriteTransaction
from .values import SnapshotPayload


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
class ActiveSelectionSource:
    id: str
    emphasis: Emphasis
    emphasis_override: Emphasis | None


@dataclass(frozen=True)
class SelectionSource:
    application_id: str
    job_analysis_id: str
    job_snapshot_id: str
    analysis: JobAnalysis
    active_analysis_id: str | None
    active_snapshot_id: str
    active_plan: ActiveSelectionSource | None
    deleted_at: str | None


class AnalysisPayloadStore(Protocol):
    """Only snapshot reads and verified provider-response preservation."""

    def read_snapshot(self, reference: str, expected_hash: str) -> str: ...

    def commit_provider_response(
        self,
        application_id: str,
        operation_id: str,
        artifact_id: str,
        sanitized_json: str,
    ) -> SnapshotPayload: ...

    def verify_payload(self, reference: str, expected_hash: str) -> str: ...


class AnalysisKnowledgeSource(Protocol):
    """Read canonical files only; the caller checks recovery state through its token."""

    def load(self) -> Knowledge: ...


class AnalysisSelectionSourceReader(Protocol):
    def knowledge_is_prepared(self, tx: ReadTransaction) -> bool: ...

    def analysis_source(
        self, tx: ReadTransaction, job_snapshot_id: str
    ) -> AnalysisSnapshotSource: ...

    def selection_source(self, tx: ReadTransaction, job_analysis_id: str) -> SelectionSource: ...


class AnalysisPlanStore(Protocol):
    def save_analysis(
        self,
        tx: WriteTransaction,
        application_id: str,
        snapshot_id: str,
        analysis: JobAnalysis,
        plan: SelectionManifest,
        *,
        provider: str,
        model: str,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        expected_analysis_id: str | None = None,
        expected_selection_plan_id: str | None = None,
        enforce_expected_selection_plan: bool = False,
        refuse_matching_context_operation: bool = False,
    ) -> tuple[str, SelectionPlan]: ...

    def create_selection_plan(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        expected_selection_plan_id: str | None = None,
        enforce_expected_selection_plan: bool = False,
        refuse_matching_context_operation: bool = False,
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan: ...

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None: ...

    def selection_plan(self, tx: ReadTransaction, selection_plan_id: str) -> SelectionPlan: ...

    def set_normalized_role(
        self, tx: WriteTransaction, application_id: str, normalized_role: str
    ) -> None: ...
