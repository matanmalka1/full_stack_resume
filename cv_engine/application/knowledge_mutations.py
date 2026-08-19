from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class KnowledgeMutationState(StrEnum):
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class StagedKnowledgeFile:
    """Opaque Workspace references and hashes for one validated file replacement."""

    mutation_id: str
    source_reference: str
    staged_reference: str
    old_sha256: str
    new_sha256: str


@dataclass(frozen=True)
class PrepareKnowledgeMutation:
    """Durable inputs required to decide a cross-store mutation after a crash."""

    mutation_id: str
    mutation_type: str
    source_reference: str
    staged_reference: str
    old_sha256: str
    new_sha256: str
    db_mutation_type: str
    db_mutation_id: str
    db_mutation: dict[str, Any]
    recovery_strategy: str


@dataclass(frozen=True)
class KnowledgeMutation:
    id: str
    mutation_type: str
    state: KnowledgeMutationState
    source_reference: str
    staged_reference: str
    old_sha256: str
    new_sha256: str
    db_mutation_type: str
    db_mutation_id: str
    db_mutation: dict[str, Any]
    recovery_strategy: str
    prepared_at: str
    committed_at: str | None
    quarantined_at: str | None
    quarantine_reason: str | None
