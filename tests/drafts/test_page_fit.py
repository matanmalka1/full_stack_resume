"""The page-fit trimming policy (product-spec §10): which line goes first, and which never."""

from __future__ import annotations

import pytest

from cv_engine.domain.contracts.drafts import (
    ClaimLine,
    ClaimStyle,
    ClaimType,
    DraftDocument,
    ResumeSection,
)
from cv_engine.domain.contracts.knowledge import (
    Fact,
    FactStatus,
    Profile,
    ResumeSectionSpec,
)
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.domain.drafts import drop_claims
from cv_engine.domain.facts import FactStore
from cv_engine.domain.frame import ROLE_BLOCK_TAG, dangling_heading
from cv_engine.domain.page_fit import next_trim, trimmed_line
from cv_engine.domain.render_validation import page_limit

_HASH = "b" * 64


def _fact(fact_id: str, style: str = "bullet", tags: list[str] | None = None) -> Fact:
    return Fact(
        fact_id=fact_id,
        meaning=fact_id,
        renderings={"en": fact_id},
        tags=tags or [],
        status=FactStatus.CANONICAL,
        provenance="test",
        resume_style=style,  # type: ignore[arg-type]
    )


def _claim(claim_id: str, style: ClaimStyle = "bullet", fact_id: str | None = None) -> ClaimLine:
    claim_type: ClaimType = "headline" if style == "headline" else "canonical"
    return ClaimLine(
        claim_id=claim_id,
        style=style,
        text=f"text of {claim_id}",
        fact_ids=[fact_id or claim_id],
        claim_type=claim_type,
        text_hash="h",
    )


def _role(prefix: str, bullets: int) -> list[ClaimLine]:
    return [
        _claim(f"{prefix}.title", "heading"),
        _claim(f"{prefix}.dates", "date"),
        *(_claim(f"{prefix}.b{index}") for index in range(1, bullets + 1)),
    ]


def _facts(draft: DraftDocument, *, role_titles: bool = True) -> FactStore:
    facts: dict[str, Fact] = {}
    for section in draft.sections:
        for claim in section.claims:
            for fact_id in claim.fact_ids:
                tags = [ROLE_BLOCK_TAG] if role_titles and fact_id.endswith(".title") else []
                facts[fact_id] = _fact(fact_id, claim.style, tags)
    return FactStore(facts, {"test": "1"})


def _spec(name: str, claims: list[ClaimLine], **changes) -> ResumeSectionSpec:
    return ResumeSectionSpec(
        name_en=name,
        name_he=name,
        fact_ids=[fact_id for claim in claims for fact_id in claim.fact_ids],
        **changes,
    )


def _profile(*specs: ResumeSectionSpec, allow_two_pages: bool = False) -> Profile:
    return Profile(
        profile_id="development.test",
        version="1",
        track=Track.DEVELOPMENT,
        profile=ProfileName.DEVELOPMENT,
        default_emphasis=Emphasis.DEVELOPMENT_BALANCED,
        allowed_emphases=[Emphasis.DEVELOPMENT_BALANCED],
        normalized_role="Full Stack Developer",
        safe_headlines=["Full Stack Developer"],
        sections=list(specs),
        allow_two_pages=allow_two_pages,
    )


def _draft(*sections: tuple[str, list[ClaimLine]]) -> DraftDocument:
    return DraftDocument(
        application_id="app",
        job_text_hash=_HASH,
        job_analysis_id="analysis",
        language="en",
        track=Track.DEVELOPMENT,
        profile=ProfileName.DEVELOPMENT,
        emphasis=Emphasis.DEVELOPMENT_BALANCED,
        name="Candidate",
        headline=_claim("headline", "headline"),
        contacts=[_claim("contact.email", "contact")],
        sections=[ResumeSection(name=name, claims=claims) for name, claims in sections],
        fact_store_version="v1",
    )


def _trim_all(draft: DraftDocument, profile: Profile, facts: FactStore) -> list[str]:
    """Every line the policy gives up, in order, until it names none."""
    dropped: list[str] = []
    while (claim_id := next_trim(draft, profile, facts)) is not None:
        dropped.append(claim_id)
        draft = drop_claims(draft, profile, {claim_id})
    return dropped


def test_page_limit_reads_the_profile() -> None:
    claims = [_claim("summary.a", "paragraph")]
    assert page_limit(_profile(_spec("Summary", claims))) == 1
    assert page_limit(_profile(_spec("Summary", claims), allow_two_pages=True)) == 2


def test_the_block_furthest_above_its_floor_loses_its_last_line() -> None:
    newer, older = _role("new", 4), _role("old", 2)
    claims = [*newer, *older]
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims, min_claims_per_role=2))
    # The newer role has two lines above its floor, the older none.
    assert next_trim(draft, profile, _facts(draft)) == "new.b4"


def test_a_tie_goes_to_the_block_later_in_the_document() -> None:
    newer, older = _role("new", 3), _role("old", 3)
    experience = [*newer, *older]
    skills = [_claim("skill.a", "item"), _claim("skill.b", "item")]
    draft = _draft(("Experience", experience), ("Skills", skills))
    profile = _profile(
        _spec("Experience", experience, min_claims_per_role=2),
        _spec("Skills", skills),
    )
    facts = _facts(draft)
    # Every block is one line above its floor: the last block - a later section - goes first.
    assert next_trim(draft, profile, facts) == "skill.b"
    draft = drop_claims(draft, profile, {"skill.b"})
    # Then the older role before the newer one.
    assert next_trim(draft, profile, facts) == "old.b3"


def test_a_role_keeps_its_minimum_and_no_heading_is_left_dangling() -> None:
    claims = [*_role("new", 4), *_role("old", 1)]
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims, min_claims_per_role=2))
    facts = _facts(draft)

    dropped = _trim_all(draft, profile, facts)

    assert dropped == ["new.b4", "new.b3"]
    trimmed = drop_claims(draft, profile, set(dropped))
    [section] = trimmed.sections
    kept = [claim.claim_id for claim in section.claims]
    # The older role was already under its floor: it keeps its one line, its title, its dates.
    assert kept == [
        "new.title",
        "new.dates",
        "new.b1",
        "new.b2",
        "old.title",
        "old.dates",
        "old.b1",
    ]
    assert dangling_heading(section.claims) is None


def test_a_role_with_no_floor_still_keeps_one_line() -> None:
    claims = _role("only", 3)
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims))
    assert _trim_all(draft, profile, _facts(draft)) == ["only.b3", "only.b2"]


def test_pinned_lines_are_never_dropped() -> None:
    claims = _role("role", 4)
    draft = _draft(("Experience", claims))
    profile = _profile(
        _spec("Experience", claims, pinned_fact_ids=["role.b3", "role.b4"], min_claims_per_role=1)
    )
    # The pinned lines count toward the role, but only unpinned lines go.
    assert _trim_all(draft, profile, _facts(draft)) == ["role.b2", "role.b1"]


def test_structure_headline_and_contacts_are_never_named() -> None:
    claims = _role("role", 1)
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims))
    assert next_trim(draft, profile, _facts(draft)) is None
    with pytest.raises(ValueError):
        drop_claims(draft, profile, {"role.dates"})
    with pytest.raises(KeyError):
        drop_claims(draft, profile, {"headline"})


def test_a_section_without_headings_keeps_one_line() -> None:
    claims = [_claim("summary.a", "paragraph"), _claim("summary.b", "paragraph")]
    draft = _draft(("Summary", claims))
    profile = _profile(_spec("Summary", claims))
    assert _trim_all(draft, profile, _facts(draft)) == ["summary.b"]


def test_an_optional_section_may_lose_every_line_and_is_then_dropped() -> None:
    summary = [_claim("summary.a", "paragraph")]
    extras = [_claim("extra.a", "item"), _claim("extra.b", "item")]
    draft = _draft(("Summary", summary), ("Extras", extras))
    profile = _profile(_spec("Summary", summary), _spec("Extras", extras, optional=True))
    facts = _facts(draft)

    dropped = _trim_all(draft, profile, facts)

    assert dropped == ["extra.b", "extra.a"]
    trimmed = drop_claims(draft, profile, set(dropped))
    assert [section.name for section in trimmed.sections] == ["Summary"]


def test_lines_above_a_sections_first_heading_may_all_go() -> None:
    claims = [_claim("intro.a", "paragraph"), *_role("role", 1)]
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims))
    assert _trim_all(draft, profile, _facts(draft)) == ["intro.a"]


def test_a_heading_that_is_not_a_role_keeps_one_line() -> None:
    claims = _role("project", 3)
    draft = _draft(("Projects", claims))
    # Not a role title, so the role floor does not apply; one line stays under it.
    profile = _profile(_spec("Projects", claims, min_claims_per_role=3))
    assert _trim_all(draft, profile, _facts(draft, role_titles=False)) == [
        "project.b3",
        "project.b2",
    ]


def test_nothing_removable_names_nothing() -> None:
    summary = [_claim("summary.a", "paragraph")]
    draft = _draft(("Summary", summary))
    profile = _profile(_spec("Summary", summary, pinned_fact_ids=["summary.a"]))
    assert next_trim(draft, profile, _facts(draft)) is None


def test_the_policy_is_deterministic_and_pure() -> None:
    claims = [*_role("new", 4), *_role("old", 4)]
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims, min_claims_per_role=1))
    facts = _facts(draft)
    before = draft.model_dump()
    assert next_trim(draft, profile, facts) == next_trim(draft, profile, facts) == "old.b4"
    assert draft.model_dump() == before


def test_a_dropped_line_reads_with_its_section_and_heading() -> None:
    claims = _role("role", 2)
    draft = _draft(("Experience", claims))
    line = trimmed_line(draft, "role.b2")
    assert (line.section, line.heading, line.text) == (
        "Experience",
        "text of role.title",
        "text of role.b2",
    )


def test_dropping_reseals_the_document() -> None:
    claims = _role("role", 2)
    draft = _draft(("Experience", claims))
    profile = _profile(_spec("Experience", claims))
    trimmed = drop_claims(draft, profile, {"role.b2"})
    assert trimmed.content_hash and trimmed.content_hash != draft.content_hash
