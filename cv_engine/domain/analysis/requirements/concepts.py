"""Requirement concept configuration and typed coverage rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ....util import canonical_json, sha256_text

_HEADING_DECORATION = " \t*_#~`-\u2013\u2014\u2022\u2023\u25aa\u25e6:?.!,"
_WHITESPACE = re.compile(r"\s+")


def heading_key(text: str) -> str:
    """Reduce a heading to its canonical marker-comparison form."""
    return _WHITESPACE.sub(" ", text.strip(_HEADING_DECORATION)).strip().casefold()


class RequirementConceptError(ValueError):
    pass


@dataclass(frozen=True)
class RequirementConcept:
    concept: str
    patterns: tuple[re.Pattern[str], ...]
    boundary_fact_ids: frozenset[str] = frozenset()


class RequirementConceptStore:
    """Structural markers, scales, and boundary applicability rules."""

    def __init__(self, payload: dict[str, Any], *, origin: str = "requirement concepts"):
        self.origin = origin
        self.scales: dict[str, tuple[str, ...]] = {
            name: tuple(str(value).casefold() for value in values)
            for name, values in (payload.get("scales") or {}).items()
        }
        self.block_markers = tuple(
            str(value).casefold() for value in payload.get("requirement_block_markers") or ()
        )
        self.mandatory_markers = tuple(
            str(value).casefold() for value in payload.get("mandatory_markers") or ()
        )
        self.preferred_markers = tuple(
            str(value).casefold() for value in payload.get("preferred_markers") or ()
        )
        self.requirement_cues = self._cues(payload, "requirement_cues", "soft_skill_cues")
        # A store with no requirement cues reads every posting as requiring
        # nothing - `absent`, the flattering answer, with full confidence. That
        # is a configuration error rather than a finding, so it is refused here
        # instead of being reported as a result.
        if not self.requirement_cues:
            raise RequirementConceptError(f"{origin}: no requirement cues declared")
        self.responsibility_cues = self._cues(payload, "responsibility_cues")
        # Which section a *bare* heading opens, keyed on the heading itself.
        # A line with no colon carries no syntactic evidence that it announces
        # anything, so it must match a configured marker outright rather than
        # merely contain one - otherwise "SaaS experience preferred" would be
        # read as a heading and the requirement in it would disappear.
        # Later entries win, so the precedence is the same as `_section_of`.
        self.heading_sections: dict[str, str] = {
            key: section
            for markers, section in (
                (self.responsibility_cues, "responsibilities"),
                (self.mandatory_markers, "requirements"),
                (self.block_markers, "requirements"),
                (self.preferred_markers, "preferred"),
            )
            for marker in markers
            for key in (heading_key(marker),)
            if key
        }
        self.concepts: dict[str, RequirementConcept] = {
            name: self._concept(name, body)
            for name, body in (payload.get("concepts") or {}).items()
        }
        if not self.concepts:
            raise RequirementConceptError(f"{origin}: no concepts declared")
        self.version = sha256_text(canonical_json(payload))

    @staticmethod
    def _cues(payload: dict[str, Any], *keys: str) -> tuple[str, ...]:
        """Every supported language's cues for these keys, as one set.

        Scoped per language in the file so each vocabulary stays readable and
        maintainable on its own, then unioned here rather than selected by the
        posting's detected language. Postings are routinely mixed - a Hebrew
        listing naming English tools and titles is the normal case, not the
        exception - and selecting one language's cues would make the other
        half's requirements invisible.

        Unioning is also the conservative direction: it can only find more
        requirement-bearing statements, which lowers completeness and reports
        less confidence, never more.
        """
        found: list[str] = []
        for key in keys:
            entry = payload.get(key) or {}
            values = (
                [value for language in sorted(entry) for value in entry[language] or ()]
                if isinstance(entry, dict)
                else list(entry)
            )
            found.extend(str(value).casefold() for value in values)
        return tuple(dict.fromkeys(found))

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
