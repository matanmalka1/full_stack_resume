"""The minimal configured mapping from requirement text to boundary facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ....util import canonical_json, sha256_text


class RequirementConceptError(ValueError):
    pass


@dataclass(frozen=True)
class RequirementConcept:
    concept: str
    patterns: tuple[re.Pattern[str], ...]
    boundary_fact_ids: frozenset[str] = frozenset()


class RequirementConceptStore:
    """Boundary applicability rules; it has no extraction or coverage authority."""

    def __init__(self, payload: dict[str, Any], *, origin: str = "requirement concepts"):
        self.origin = origin
        self.concepts: dict[str, RequirementConcept] = {
            name: self._concept(name, body)
            for name, body in (payload.get("concepts") or {}).items()
        }
        if not self.concepts:
            raise RequirementConceptError(f"{origin}: no concepts declared")
        self.version = sha256_text(canonical_json(payload))

    @classmethod
    def from_payload(
        cls, payload: dict[str, Any], *, origin: str = "requirement concepts"
    ) -> RequirementConceptStore:
        return cls(payload, origin=origin)

    def _concept(self, name: str, body: dict[str, Any]) -> RequirementConcept:
        patterns = tuple(
            re.compile(str(pattern), re.IGNORECASE) for pattern in body.get("patterns") or ()
        )
        if not patterns:
            raise RequirementConceptError(f"{self.origin}: concept {name} declares no patterns")
        return RequirementConcept(
            concept=name,
            patterns=patterns,
            boundary_fact_ids=frozenset(body.get("boundary_fact_ids") or ()),
        )
