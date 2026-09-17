"""§14: provider wording for one section or one claim, over a frozen version."""

from __future__ import annotations

from dataclasses import dataclass

from ....domain.contracts.drafts import DraftDocument, WorkingDraft
from ..proposals import ProviderEvidence


@dataclass(frozen=True)
class PreparedRegeneration:
    """One accepted regeneration, computed but not yet committed.

    The document already carries the proposed wording: it passed
    `apply_proposed_claims`, which is the same authority a manual edit passes,
    so anything unsupported was refused before this value could exist. What is
    left is the optimistic commit against the exact version that was frozen.
    """

    working: WorkingDraft
    source: DraftDocument
    claim_ids: list[str]
    evidence: ProviderEvidence
