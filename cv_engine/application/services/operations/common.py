"""The Knowledge hash an analysis Operation's frozen sources are compared against.

It is used on the way in, when a submission records what it depended on, and
again on the way out, when a handler checks whether that dependency still holds.
Keeping it here is what makes those two comparisons the same computation rather
than two spellings of it.
"""

from __future__ import annotations

from ....domain.knowledge import Knowledge


def analysis_knowledge_context_hash(knowledge: Knowledge) -> str:
    """Everything an analysis may have read, including the requirement vocabulary."""
    return knowledge.context_hash()
