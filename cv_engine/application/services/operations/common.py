"""The two hashes an Operation's frozen sources are compared against.

Both are used on the way in, when a submission records what it depended on,
and again on the way out, when a handler checks whether that dependency still
holds. Keeping them here is what makes those two comparisons the same
computation rather than two spellings of it.
"""

from __future__ import annotations

from ....util import canonical_json, sha256_text
from ..analysis import AnalysisService


def analysis_knowledge_context_hash(service: AnalysisService) -> str:
    return sha256_text(canonical_json(service.load_knowledge().versions()))


def _model_hash(value) -> str:
    return sha256_text(canonical_json(value.model_dump(mode="json")))
