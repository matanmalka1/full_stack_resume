"""Requirement concept configuration and typed coverage rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ....util import canonical_json, sha256_text
from ...models import RequirementKind

_HEADING_DECORATION = " \t*_#~`-\u2013\u2014\u2022\u2023\u25aa\u25e6:?.!,"
_WHITESPACE = re.compile(r"\s+")


def heading_key(text: str) -> str:
    """Reduce a heading to its canonical marker-comparison form."""
    return _WHITESPACE.sub(" ", text.strip(_HEADING_DECORATION)).strip().casefold()


class RequirementConceptError(ValueError):
    pass


@dataclass(frozen=True)
class ConceptComponent:
    """One named part of a compositional requirement.

    A component with no satisfying facts or tags is not a modelling mistake: it
    states that nothing in canonical Knowledge can establish this part. That is
    how "sales carried out at a technology company" stays honestly missing
    instead of being satisfied by finding a sales fact and a technology fact
    separately.
    """

    component_id: str
    label: str
    satisfied_by_fact_ids: frozenset[str] = frozenset()
    satisfied_by_tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RequirementConcept:
    concept: str
    label: str
    kind: RequirementKind
    patterns: tuple[re.Pattern[str], ...]
    components: tuple[ConceptComponent, ...] = ()
    satisfied_by_fact_ids: frozenset[str] = frozenset()
    satisfied_by_tags: frozenset[str] = frozenset()
    boundary_fact_ids: frozenset[str] = frozenset()
    candidate_fact_ids: frozenset[str] = frozenset()
    candidate_tags: frozenset[str] = frozenset()
    scale: str = ""
    demand_terms: dict[str, tuple[str, ...]] = field(default_factory=dict)
    demand_pattern: re.Pattern[str] | None = None
    value_fact_ids: tuple[str, ...] = ()
    value_source: str = ""


class RequirementConceptStore:
    """The requirement vocabulary and its typed coverage rules.

    Versioned like every other Knowledge dependency so that changing what a
    requirement means is visible as a change, rather than silently reshaping
    analyses that were already committed.
    """

    def __init__(self, payload: dict[str, Any], *, origin: str = "requirement concepts"):
        self.origin = origin
        self.policy_version = str(payload.get("policy_version", ""))
        self.extraction_version = str(payload.get("extraction_version", ""))
        if not self.extraction_version:
            raise RequirementConceptError(f"{origin}: extraction_version is required")
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
        kind = body.get("kind")
        if kind not in {"threshold", "compositional", "presence"}:
            raise RequirementConceptError(
                f"{self.origin}: concept {name} has unknown kind {kind!r}"
            )
        patterns = tuple(
            re.compile(str(pattern), re.IGNORECASE) for pattern in body.get("patterns") or ()
        )
        if not patterns:
            raise RequirementConceptError(f"{self.origin}: concept {name} declares no patterns")
        scale = str(body.get("scale", ""))
        if kind == "threshold" and not scale:
            raise RequirementConceptError(f"{self.origin}: threshold concept {name} needs a scale")
        if scale and scale != "years" and scale not in self.scales:
            raise RequirementConceptError(
                f"{self.origin}: concept {name} names unknown scale {scale!r}"
            )
        if kind == "compositional" and not body.get("components"):
            raise RequirementConceptError(
                f"{self.origin}: compositional concept {name} declares no components"
            )
        demand = body.get("demand_pattern")
        return RequirementConcept(
            concept=name,
            label=str(body.get("label", name)),
            kind=kind,
            patterns=patterns,
            components=tuple(
                ConceptComponent(
                    component_id=str(item["component_id"]),
                    label=str(item.get("label", item["component_id"])),
                    satisfied_by_fact_ids=frozenset(item.get("satisfied_by_fact_ids") or ()),
                    satisfied_by_tags=frozenset(item.get("satisfied_by_tags") or ()),
                )
                for item in body.get("components") or ()
            ),
            satisfied_by_fact_ids=frozenset(body.get("satisfied_by_fact_ids") or ()),
            satisfied_by_tags=frozenset(body.get("satisfied_by_tags") or ()),
            boundary_fact_ids=frozenset(body.get("boundary_fact_ids") or ()),
            candidate_fact_ids=frozenset(body.get("candidate_fact_ids") or ()),
            candidate_tags=frozenset(body.get("candidate_tags") or ()),
            scale=scale,
            demand_terms={
                str(level): tuple(str(term).casefold() for term in terms)
                for level, terms in (body.get("demand_terms") or {}).items()
            },
            demand_pattern=re.compile(str(demand), re.IGNORECASE) if demand else None,
            value_fact_ids=tuple(body.get("value_fact_ids") or ()),
            value_source=str(body.get("value_source", "")),
        )
