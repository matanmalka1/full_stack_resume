"""Ports the document's content services read through, besides the document store.

The document itself is reached through `ports/documents.py`. What stays here is what
the provenance export needs from elsewhere: the Application's labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .transactions import ReadTransaction


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
