"""The Knowledge fact lifecycle, split from the mutation engine underneath it.

`KnowledgeService` is the whole public surface and the import path did not
move. Behind it, `mutations` holds the two-phase commit and its crash recovery
- the one part of this package whose defects are not regenerable - and
`service` holds the fact lifecycle commands and reads that drive it.
"""

from __future__ import annotations

from .mutations import KnowledgeMutationEngine
from .service import KnowledgeService

__all__ = [
    "KnowledgeMutationEngine",
    "KnowledgeService",
]
