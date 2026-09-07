"""Knowledge/Facts boundary DTOs: consumed exclusively by `KnowledgeService`."""

from __future__ import annotations

from typing import Any

from ...domain.contracts.knowledge import Fact
from ...domain.contracts.selection import SelectionPlan
from ._base import BoundaryDTO


class KnowledgeVersionsResult(BoundaryDTO):
    facts: str
    facts_lifecycle: str
    profiles: str
    emphasis_policies: str
    presentations: str
    candidate_context: str
    requirement_concepts: str


class FactEventView(BoundaryDTO):
    id: str
    fact_id: str
    source_file: str
    event_type: str
    from_status: str | None
    to_status: str
    application_id: str | None
    claim_id: str | None
    reason: str
    fact_hash: str
    facts_version: str
    lifecycle_version: str
    created_at: str


class FactListItem(BoundaryDTO):
    fact: Fact
    recorded_status: str | None = None


class FactListResult(BoundaryDTO):
    items: list[FactListItem]


class FactDetailResult(BoundaryDTO):
    fact: Fact
    events: list[FactEventView]


class FactHistoryResult(BoundaryDTO):
    events: list[FactEventView]


class FactMutationResult(BoundaryDTO):
    fact: Fact
    event_id: str
    facts_version: str
    lifecycle_version: str


class FactAttachmentResult(FactMutationResult):
    profile: str
    section: str
    pinned: bool
    profile_source: str
    profile_store_version: str


class ConfirmAndUseFactResult(BoundaryDTO):
    fact: Fact
    event_ids: list[str]
    selection_plan: SelectionPlan
    facts_version: str
    lifecycle_version: str
    profile_store_version: str


class FactReconciliationResult(BoundaryDTO):
    passed: bool
    fact_counts: dict[str, int]
    tracked_facts: int
    facts_version: str
    lifecycle_version: str
    problems: list[str]
    journal_prepared: int = 0
    journal_quarantined: int = 0


def fact_event_view(record: dict[str, Any]) -> FactEventView:
    """Strip persistence-only payload columns from one audit row."""
    return FactEventView.model_validate(
        {key: record.get(key) for key in FactEventView.model_fields}
    )
