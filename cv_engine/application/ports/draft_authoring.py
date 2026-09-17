"""Authoring sources and durable provider-evidence preservation."""

from __future__ import annotations

from typing import Protocol

from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.providers import ProviderTaskResult
from ..chain import DraftChainSources
from ..services.proposals import ProviderEvidence
from .transactions import ReadTransaction


class DraftAuthoringSourceReader(Protocol):
    def analysis_source(self, tx: ReadTransaction, analysis_id: str) -> dict: ...

    def active_snapshot_id(self, tx: ReadTransaction, application_id: str) -> str: ...

    def snapshot_source(self, tx: ReadTransaction, snapshot_id: str) -> dict: ...

    def deleted_at(self, tx: ReadTransaction, application_id: str) -> str | None: ...

    def chain_source(
        self, tx: ReadTransaction, application_id: str, draft: DraftDocument
    ) -> DraftChainSources: ...


class DraftEvidencePreserver(Protocol):
    """External payload preservation followed by durable inactive registration."""

    def preserve(
        self, application_id: str, operation_id: str, task: str, provenance: ProviderTaskResult
    ) -> ProviderEvidence: ...
