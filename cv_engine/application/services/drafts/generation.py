"""Generating the working draft: deterministic composition, then optional wording."""

from __future__ import annotations

from dataclasses import dataclass

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.drafts import DraftDocument
from ....domain.knowledge import Knowledge
from ....domain.validation import validate_draft as run_draft_validation
from ..proposals import ProviderEvidence

__all__ = ["DeterministicRun", "PreparedDraft", "run_draft_validation"]


@dataclass(frozen=True)
class PreparedDraft:
    source: DraftDocument
    analysis: JobAnalysis
    plan_id: str
    knowledge: Knowledge
    evidence: ProviderEvidence | None = None


@dataclass(frozen=True)
class DeterministicRun:
    """What produced a draft when no provider was involved.

    `none` rather than a contract and prompt version, which is what this record
    carried before Stage G. The deterministic composer runs under no AI task
    contract and reads no prompt, so naming one was a value the run never had -
    and it was typed in beside a contract file nothing read, so it could not
    even be wrong consistently. The column is `NOT NULL`, so the honest answer
    is a literal that says there was none.
    """

    provider: str = "deterministic"
    model: str = "rules-v1"
    task_contract_version: str = "none"
    prompt_version: str = "none"
