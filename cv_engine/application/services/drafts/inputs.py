"""Prepared Operation values for document generation and regeneration."""

from __future__ import annotations

from dataclasses import dataclass

from ....domain.contracts.drafts import DraftDocument
from ....domain.contracts.selection import SelectionManifest
from ..proposals import ProviderEvidence


@dataclass(frozen=True)
class PreparedDraft:
    """Generated content, computed but not written.

    Activation writes `content` only while the document still holds
    `expected_document_hash` (§14): anything that changed the document while this
    ran discards it. `selection` is the AI-proposed selection the content was
    composed from, written with it; `None` keeps the document's own.
    """

    application_id: str
    expected_document_hash: str
    content: DraftDocument
    evidence: ProviderEvidence
    review_evidence: ProviderEvidence | None = None
    selection: SelectionManifest | None = None
    selection_evidence: ProviderEvidence | None = None


@dataclass(frozen=True)
class PreparedRegeneration:
    """One accepted regeneration, computed but not yet committed.

    The content already carries the proposed wording: it passed
    `apply_proposed_claims`, the same authority a manual edit passes, so anything
    unsupported was refused before this value could exist. What is left is the
    optimistic commit against the exact document hash that was read.
    """

    application_id: str
    expected_document_hash: str
    content: DraftDocument
    claim_ids: list[str]
    evidence: ProviderEvidence
    review_evidence: ProviderEvidence | None = None
