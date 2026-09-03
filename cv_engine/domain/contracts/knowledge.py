"""Canonical fact, candidate-context, and profile contracts."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .base import StrictModel
from .taxonomy import Emphasis, ProfileName, Track


class FactStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANONICAL = "canonical"


class Fact(StrictModel):
    fact_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    meaning: str = Field(min_length=1)
    renderings: dict[str, str]
    tags: list[str]
    status: FactStatus
    provenance: str = Field(min_length=1)
    confirmed_at: str | None = None
    effective_dates: str | None = None
    replaces: str | None = None
    source_file: str = ""
    resume_style: Literal["paragraph", "heading", "date", "bullet", "item", "contact"]
    # The absolute address a rendering stands for, where the rendering is
    # display text rather than the address itself: "linkedin.com/in/..." is
    # what a CV shows, "https://www.linkedin.com/in/..." is what the link must
    # point at. Declaring it here keeps the address in the fact's one canonical
    # location instead of a second copy beside it.
    link_target: str | None = None

    @model_validator(mode="after")
    def require_english_rendering(self) -> Fact:
        if not self.renderings.get("en"):
            raise ValueError("every fact requires an English rendering")
        return self

    @model_validator(mode="after")
    def link_target_carries_the_rendering(self) -> Fact:
        """A declared address must still be the one the fact displays.

        Without this the two halves of the same fact can drift apart and the
        CV shows one profile while linking to another.
        """
        if self.link_target is None:
            return self
        if not self.link_target.startswith("https://"):
            raise ValueError(f"link target is not https: {self.link_target}")
        if self.renderings["en"] not in self.link_target:
            raise ValueError(
                f"link target {self.link_target} does not carry the fact's "
                f"English rendering {self.renderings['en']!r}"
            )
        return self


class FactSource(StrictModel):
    source_version: str
    facts: list[Fact]

    @model_validator(mode="after")
    def require_unique_fact_ids(self) -> FactSource:
        duplicates = sorted(
            fact_id
            for fact_id, count in Counter(fact.fact_id for fact in self.facts).items()
            if count > 1
        )
        if duplicates:
            raise ValueError(f"fact source repeats fact IDs: {duplicates}")
        return self


class ResumeSectionSpec(StrictModel):
    """A section's candidate pool, not its output.

    `fact_ids` is everything this section is *allowed* to say; the selection
    policy chooses a subset of it under `max_claims`. `pinned_fact_ids` names
    the non-structural facts that must survive regardless of score — the ones
    that keep a role block from rendering as a heading with no evidence.
    Structural facts (headings, dates, contacts) are pinned implicitly.

    A section budget alone says nothing about how the budget is spread across
    the roles inside it, so a long, senior role can end up with two bullets
    while an older one takes seven. `min_claims_per_role` and
    `min_quantitative_per_role` are floors each role block must reach before
    the rest of the budget is handed out by rank, and `max_claims_per_role` is
    the ceiling that stops one role absorbing what is left: an older role
    carrying seven bullets under a newer one carrying two reads as a career
    running backwards, however the ranking got there.
    """

    name_en: str
    name_he: str
    fact_ids: list[str]
    pinned_fact_ids: list[str] = []
    max_claims: int | None = None
    min_claims_per_role: int = 0
    min_quantitative_per_role: int = 0
    max_claims_per_role: int | None = None
    optional: bool = False

    @model_validator(mode="after")
    def validate_pool(self) -> ResumeSectionSpec:
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError(f"section {self.name_en!r} repeats a candidate fact")
        if self.min_claims_per_role < 0 or self.min_quantitative_per_role < 0:
            raise ValueError(f"section {self.name_en!r} has a negative role-block floor")
        if self.max_claims_per_role is not None:
            ceiling = self.max_claims_per_role
            if ceiling < max(self.min_claims_per_role, self.min_quantitative_per_role):
                raise ValueError(f"section {self.name_en!r} caps a role block below its own floor")
        outside = sorted(set(self.pinned_fact_ids) - set(self.fact_ids))
        if outside:
            raise ValueError(f"section {self.name_en!r} pins facts outside its pool: {outside}")
        if self.max_claims is not None:
            if self.max_claims < 1:
                raise ValueError(f"section {self.name_en!r} has a non-positive claim budget")
            if self.max_claims > len(self.fact_ids):
                raise ValueError(
                    f"section {self.name_en!r} budgets more claims than its pool holds"
                )
        return self


class EmphasisPolicy(StrictModel):
    """How one Emphasis weights the shared canonical tag vocabulary.

    Emphasis is orthogonal to Profile, so its policy lives once here rather than
    being copied into every Profile that allows it. `preferred_tags` is a
    coverage expectation, not a structural invariant: unlike `Profile.required_tags`
    it never forces a fact into the document, it only reports when the selected
    content drifted away from what the Emphasis is supposed to be about.
    """

    emphasis: Emphasis
    tag_weights: dict[str, int]
    preferred_tags: list[str] = []
    minimum_coverage: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_coverage(self) -> EmphasisPolicy:
        if any(weight < 0 for weight in self.tag_weights.values()):
            raise ValueError(f"emphasis {self.emphasis} has a negative tag weight")
        if self.minimum_coverage > len(self.preferred_tags):
            raise ValueError(
                f"emphasis {self.emphasis} requires more coverage than it has preferred tags"
            )
        return self


class Profile(StrictModel):
    profile_id: str
    version: str
    track: Track
    profile: ProfileName
    default_emphasis: Emphasis
    allowed_emphases: list[Emphasis]
    normalized_role: str
    safe_headlines: list[str]
    # What the CV says under the name. `normalized_role` stays the filing name —
    # the PDF filename and role folder — so a headline written for a reader
    # ("Technical Sales | B2B Sales | Software Background") does not leak into
    # the artifact path.
    headline: str | None = None
    required_tags: list[str] = []
    tag_weights: dict[str, int] = {}
    # The dated roles this Profile deliberately does not offer, each against the
    # reason it does not. Employment-history coverage is checked against the
    # fact store, so a dated role that is neither offered nor named here fails
    # the profile set instead of quietly vanishing from the CV. A waiver records
    # a decision about the head or tail of the timeline; it cannot buy off a
    # hole between two roles the Profile does offer.
    omitted_roles: dict[str, str] = {}
    sections: list[ResumeSectionSpec]
    allow_two_pages: bool = False

    @model_validator(mode="after")
    def validate_default_emphasis(self) -> Profile:
        if self.default_emphasis not in self.allowed_emphases:
            raise ValueError("default emphasis must be allowed")
        if self.headline is not None and self.headline not in self.safe_headlines:
            raise ValueError("headline must be one of the safe headlines")
        if self.normalized_role not in self.safe_headlines:
            raise ValueError("normalized role must be a safe headline")
        return self

    @model_validator(mode="after")
    def validate_omitted_role_reasons(self) -> Profile:
        """A declined role states why, so the waiver records a decision.

        Without this the reason is decoration: `{"role": ""}` would satisfy the
        coverage rule and leave the omission as unexplained as never declaring
        it. An empty string is what an absent-minded edit produces, which is
        precisely the case the waiver list exists to catch.
        """
        blank = sorted(
            fact_id for fact_id, reason in self.omitted_roles.items() if not reason.strip()
        )
        if blank:
            raise ValueError(f"omitted roles need a reason: {', '.join(blank)}")
        return self


ContactScheme = Literal["text", "mailto", "tel", "https"]


class CandidateContext(StrictModel):
    """Who this application is about, expressed as references rather than literals.

    The candidate's name and contacts stay canonical facts with one location.
    This context only says which fact plays which role, how a contact becomes a
    link, and how the recruiter-facing filename is built, so no renderer,
    validator, or filename policy contains a candidate literal.

    `names`, `link_targets`, and `resolved_filename_name` are resolved from the
    canonical facts at load time. They are a projection of those facts, never a
    second place to edit them.
    """

    context_version: str
    name_fact_id: str
    filename_name: str | None = None
    filename_language: Literal["en", "he"] = "en"
    locale: str
    timezone: str
    contact_fact_ids: list[str]
    track_contact_fact_ids: dict[str, list[str]] = {}
    link_schemes: dict[str, ContactScheme] = {}
    # `mailto`/`tel` addresses are the fact's own rendering. A profile URL is
    # not: its canonical rendering is display text ("linkedin.com/in/..."), so
    # the absolute target lives on the fact as `link_target` and is resolved
    # into this projection at load time. The context decides which scheme wraps
    # a contact; it never carries a second copy of the address.
    link_targets: dict[str, str] = {}
    names: dict[str, str] = {}
    resolved_filename_name: str = ""
    version_hash: str = ""

    def contacts_for_track(self, track: str) -> list[str]:
        extra = [
            fact_id
            for fact_id in self.track_contact_fact_ids.get(track, [])
            if fact_id not in self.contact_fact_ids
        ]
        return [*self.contact_fact_ids, *extra]

    def display_name(self, language: str) -> str:
        try:
            return self.names[language]
        except KeyError as exc:
            raise ValueError(
                f"candidate fact {self.name_fact_id} has no {language!r} rendering"
            ) from exc

    def scheme(self, fact_id: str) -> ContactScheme:
        return self.link_schemes.get(fact_id, "text")
