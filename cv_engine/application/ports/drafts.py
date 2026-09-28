"""Ports the document's content services read through, besides the document store.

The document itself is reached through `ports/documents.py`. What stays here is what
authoring and the provenance export need from elsewhere: provider evidence
preservation, and the Application's labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.providers import ProviderTaskResult
from ..services.proposals import ProviderEvidence
from .transactions import ReadTransaction


class DraftEvidencePreserver(Protocol):
    """External payload preservation followed by durable inactive registration."""

    def preserve(
        self, application_id: str, operation_id: str, task: str, provenance: ProviderTaskResult
    ) -> ProviderEvidence: ...


@dataclass(frozen=True)
class DraftHistoryApplication:
    company: str
    target_role: str
    deleted_at: str | None


class DraftHistoryApplicationReader(Protocol):
    """The Application's labels for the provenance export, read in one transaction."""

    def history_application(
        self, tx: ReadTransaction, application_id: str
    ) -> DraftHistoryApplication: ...
