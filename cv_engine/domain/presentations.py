from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from ..util import canonical_json, sha256_text
from .contracts.base import StrictModel
from .contracts.drafts import ClaimStyle
from .contracts.knowledge import Profile
from .contracts.taxonomy import Emphasis, ProfileName
from .facts import FactStore


class PresentationError(ValueError):
    pass


class PresentationRule(StrictModel):
    """A deterministic, profile-specific presentation of canonical facts.

    The rule may shorten or combine facts, but it cannot introduce an unlinked
    claim: every emitted line retains the exact supporting fact IDs, and the
    validator reproduces the wording from this version-controlled rule.
    """

    rule_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    version: str
    profile: ProfileName
    section: str
    emphases: list[Emphasis] = []
    fact_ids: list[str] = Field(min_length=1)
    style: Literal["paragraph", "bullet", "item"]
    renderings: dict[str, str]

    @model_validator(mode="after")
    def validate_rule(self) -> PresentationRule:
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError(f"presentation {self.rule_id} repeats a fact ID")
        if not self.renderings.get("en"):
            raise ValueError(f"presentation {self.rule_id} requires an English rendering")
        return self


class PresentationRules(StrictModel):
    schema_version: str
    rules: list[PresentationRule]


@dataclass(frozen=True)
class PresentedClaim:
    style: ClaimStyle
    text: str
    fact_ids: tuple[str, ...]
    rule_id: str | None = None
    rule_version: str | None = None


class PresentationStore:
    def __init__(self, payload: PresentationRules, facts: FactStore):
        self.schema_version = payload.schema_version
        self.rules = payload.rules
        self.version = sha256_text(canonical_json(payload.model_dump(mode="json")))
        self._rules = {(rule.rule_id, rule.version): rule for rule in self.rules}
        if len(self._rules) != len(self.rules):
            raise PresentationError("duplicate presentation rule identity")
        for rule in self.rules:
            support = [facts.get(fact_id, canonical_only=True) for fact_id in rule.fact_ids]
            invalid = sorted(
                {fact.resume_style for fact in support if fact.resume_style != rule.style}
            )
            if invalid:
                raise PresentationError(
                    f"presentation {rule.rule_id} style {rule.style!r} does not match facts: {invalid}"
                )

    @classmethod
    def from_payload(
        cls, payload: dict, facts: FactStore, *, origin: str = "presentation rules"
    ) -> PresentationStore:
        """Build the store from an already-read rules document.

        Locating and reading it belongs to the storage adapter; whether a rule
        set is coherent against the facts it presents stays here.
        """
        try:
            rules = PresentationRules.model_validate(payload)
        except ValueError as exc:
            raise PresentationError(f"invalid presentation rules {origin}: {exc}") from exc
        return cls(rules, facts)

    def line_groups(
        self,
        profile: Profile,
        emphasis: Emphasis,
    ) -> dict[str, list[tuple[str, ...]]]:
        """Per section, the fact groups that would be emitted as one line.

        Selection states role-block floors and ceilings in lines, so it needs
        this before it chooses: two facts a rule combines cost one line, not two.
        """
        groups: dict[str, list[tuple[str, ...]]] = {}
        for rule in self.rules:
            if rule.profile is not profile.profile:
                continue
            if rule.emphases and emphasis not in rule.emphases:
                continue
            if len(rule.fact_ids) < 2:
                continue
            groups.setdefault(rule.section, []).append(tuple(rule.fact_ids))
        return groups

    def render_rule(
        self,
        rule_id: str,
        version: str,
        fact_ids: list[str],
        language: str,
        style: str,
    ) -> str:
        try:
            rule = self._rules[(rule_id, version)]
        except KeyError as exc:
            raise PresentationError(f"unknown presentation rule: {rule_id}@{version}") from exc
        if rule.fact_ids != fact_ids:
            raise PresentationError(
                f"presentation {rule_id}@{version} requires {rule.fact_ids}, got {fact_ids}"
            )
        if rule.style != style:
            raise PresentationError(
                f"presentation {rule_id}@{version} requires style {rule.style!r}, got {style!r}"
            )
        try:
            return rule.renderings[language]
        except KeyError as exc:
            raise PresentationError(
                f"presentation {rule_id}@{version} has no {language!r} rendering"
            ) from exc

    def render_section(
        self,
        *,
        profile: Profile,
        section: str,
        emphasis: Emphasis,
        selected_fact_ids: list[str],
        language: str,
        facts: FactStore,
    ) -> list[PresentedClaim]:
        allowed = next(spec for spec in profile.sections if spec.name_en == section)
        matching = [
            rule
            for rule in self.rules
            if rule.profile is profile.profile
            and rule.section == section
            and (not rule.emphases or emphasis in rule.emphases)
            and set(rule.fact_ids) <= set(selected_fact_ids)
        ]
        for rule in matching:
            outside = sorted(set(rule.fact_ids) - set(allowed.fact_ids))
            if outside:
                raise PresentationError(
                    f"presentation {rule.rule_id} uses facts outside {profile.profile}/{section}: {outside}"
                )
            # A combined line is emitted where its first fact sits, so the facts
            # it consumes must be neighbours in what this document actually
            # says. Combining facts with a third selected fact between them
            # would reorder the section around that third fact, silently
            # breaking chronology.
            positions = [selected_fact_ids.index(fact_id) for fact_id in rule.fact_ids]
            if positions != list(range(positions[0], positions[0] + len(positions))):
                raise PresentationError(
                    f"presentation {rule.rule_id} combines facts that are not adjacent in "
                    f"{profile.profile}/{section}"
                )

        consumed: set[str] = set()
        result: list[PresentedClaim] = []
        for fact_id in selected_fact_ids:
            if fact_id in consumed:
                continue
            candidates = [rule for rule in matching if rule.fact_ids[0] == fact_id]
            if len(candidates) > 1:
                identities = [f"{rule.rule_id}@{rule.version}" for rule in candidates]
                raise PresentationError(
                    f"ambiguous presentation rules for {profile.profile}/{section}/{fact_id}: {identities}"
                )
            if candidates:
                rule = candidates[0]
                overlap = consumed & set(rule.fact_ids)
                if overlap:
                    raise PresentationError(
                        f"presentation {rule.rule_id} overlaps already-consumed facts: {sorted(overlap)}"
                    )
                result.append(
                    PresentedClaim(
                        style=rule.style,
                        text=self.render_rule(
                            rule.rule_id,
                            rule.version,
                            rule.fact_ids,
                            language,
                            rule.style,
                        ),
                        fact_ids=tuple(rule.fact_ids),
                        rule_id=rule.rule_id,
                        rule_version=rule.version,
                    )
                )
                consumed.update(rule.fact_ids)
                continue
            fact = facts.get(fact_id, canonical_only=True)
            result.append(
                PresentedClaim(
                    style=fact.resume_style,
                    text=facts.rendering(fact_id, language),
                    fact_ids=(fact_id,),
                )
            )
            consumed.add(fact_id)
        return result
