"""The hashes an Operation's frozen sources are compared against.

Both are used on the way in, when a submission records what it depended on,
and again on the way out, when a handler checks whether that dependency still
holds. Keeping them here is what makes those two comparisons the same
computation rather than two spellings of it.
"""

from __future__ import annotations

from ....util import canonical_json, sha256_text
from ..analysis import AnalysisService


def analysis_knowledge_context_hash(service: AnalysisService) -> str:
    """Everything an analysis may have read, including the requirement vocabulary."""
    return service.load_knowledge().context_hash()


def document_knowledge_context_hash(service) -> str:
    """What a draft, a plan proposal, a regeneration and a render depend on.

    The requirement vocabulary is deliberately absent: none of these stages
    reads it, and including it failed submissions at activation because a file
    they never opened had changed.
    """
    return service.load_knowledge().document_context_hash()


def _model_hash(value) -> str:
    return sha256_text(canonical_json(value.model_dump(mode="json")))
