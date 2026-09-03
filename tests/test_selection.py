"""Selection must actually select.

Every test here guards a property that was silently false before selection
existed: Profiles listed the facts that would be printed, so Emphasis, job text,
keywords and gaps could not change a single line of the document.
"""

from __future__ import annotations

import pytest
from helpers import PAYME_TECH_SALES_JOB
from pydantic import ValidationError

from cv_engine.domain.draft_markdown import serialize_markdown
from cv_engine.domain.facts import FactStore
from cv_engine.domain.models import (
    Coverage,
    Emphasis,
    Gap,
    Profile,
    Requirement,
    SelectionCandidate,
)
from cv_engine.domain.profiles import ProfileStore
from cv_engine.domain.selection import (
    STRUCTURAL_STYLES,
    MissingFactRendering,
    SelectionError,
    build_selection,
)
from cv_engine.infrastructure.rendering import normalized_role_filename

ACCOUNT_MANAGER_JOB = (
    "Account Manager for B2B customers: retention, portfolio growth, renewals, "
    "negotiation and new business."
)


def _body(draft) -> str:
    """The document without its front matter.

    Emphasis is written into the front matter, so `content_hash` differs between
    Emphases even when the CV is word-for-word identical. Comparing bodies is
    what actually proves the content changed.
    """
    return serialize_markdown(draft).split("---", 2)[2]


def test_emphasis_changes_the_selected_facts(draft_factory) -> None:
    drafts = {
        emphasis: draft_factory(
            ACCOUNT_MANAGER_JOB,
            profile_override="account-manager",
            emphasis_override=emphasis,
        ).draft
        for emphasis in (
            "account-growth",
            "new-business",
            "balanced-sales",
            "tech-consultative-sales",
        )
    }

    selections = {emphasis: tuple(draft.selected_fact_ids) for emphasis, draft in drafts.items()}
    bodies = {emphasis: _body(draft) for emphasis, draft in drafts.items()}

    assert len(set(selections.values())) == len(selections)
    assert len(set(bodies.values())) == len(bodies)


def test_selection_is_deterministic_and_ignores_irrelevant_metadata(draft_factory) -> None:
    first = draft_factory(ACCOUNT_MANAGER_JOB, profile_override="account-manager").draft
    again = draft_factory(ACCOUNT_MANAGER_JOB, profile_override="account-manager").draft
    other_ids = draft_factory(
        ACCOUNT_MANAGER_JOB,
        profile_override="account-manager",
        application_id="app-other",
        job_snapshot_id="snapshot-other",
    ).draft

    assert first.selected_fact_ids == again.selected_fact_ids
    assert _body(first) == _body(again)
    assert first.selected_fact_ids == other_ids.selected_fact_ids


def test_job_keywords_cannot_outrank_profile_and_emphasis_semantics(draft_factory) -> None:
    """Keyword stuffing may break ties; it may not reorder the policy.

    `retention` is a term the classifier extracts from a posting, and the fact it
    matches is one a new-business Emphasis deliberately scores near zero. Repeating
    it must not lift that fact over one the Emphasis considers central.
    """
    stuffed = draft_factory(
        "Account Manager. retention retention retention retention retention. "
        "Renewals and retention focus, retention metrics, retention reviews.",
        profile_override="account-manager",
        emphasis_override="new-business",
    ).draft

    scores = {candidate.fact_id: candidate for candidate in stuffed.selection.candidates}
    assert scores["sales.achievement.retention"].keyword_hits > 0
    assert (
        scores["sales.achievement.retention"].semantic_score
        < scores["sales.achievement.complex_deals"].semantic_score
    )
    assert scores["sales.achievement.retention"].outcome == "omitted"
    assert scores["sales.achievement.complex_deals"].outcome == "selected"


def test_a_required_tag_is_rescued_and_the_eviction_is_recorded(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """A Profile invariant outranks the Emphasis that would have dropped it."""
    base = profile_store.get("account-manager")
    profile = Profile.model_validate(
        {
            **base.model_dump(mode="json"),
            "required_tags": ["retention"],
        }
    )
    analysis = classify(
        ACCOUNT_MANAGER_JOB, profile_override="account-manager", emphasis_override="new-business"
    )

    selected, manifest = build_selection(
        analysis=analysis,
        profile=profile,
        policy=policy_store.get(Emphasis.NEW_BUSINESS),
        policy_store_version=policy_store.version,
        facts=fact_store,
    )

    assert "sales.achievement.retention" in selected["Core Skills"]
    outcomes = {candidate.fact_id: candidate for candidate in manifest.candidates}
    assert outcomes["sales.achievement.retention"].outcome == "rescued"
    evicted = [
        candidate.fact_id
        for candidate in manifest.candidates
        if candidate.reason == "evicted_by_required_tag_rescue"
    ]
    assert evicted == ["sales.achievement.complex_deals"]
    assert manifest.required_tag_coverage["retention"] == ["sales.achievement.retention"]


def test_structure_survives_every_profile_and_emphasis(
    profile_store: ProfileStore, draft_factory
) -> None:
    """Budgets, pins and role blocks hold across the whole matrix.

    Selection is allowed to drop bullets; it is not allowed to overrun a section,
    lose a pinned fact, or leave a role heading with no evidence under it.
    """
    for profile in profile_store.profiles.values():
        for emphasis in profile.allowed_emphases:
            setup = draft_factory(
                ACCOUNT_MANAGER_JOB,
                profile_override=profile.profile.value,
                track_override=profile.track.value,
                emphasis_override=emphasis.value,
            )
            for section, spec in zip(setup.draft.sections, profile.sections, strict=True):
                label = f"{profile.profile.value}/{emphasis.value}/{spec.name_en}"
                linked = [fact_id for claim in section.claims for fact_id in claim.fact_ids]
                assert section.claims, label
                assert len(section.claims) <= (spec.max_claims or len(spec.fact_ids)), label
                assert set(spec.pinned_fact_ids) <= set(linked), label
                assert set(linked) <= set(spec.fact_ids), label
                assert linked == [fact_id for fact_id in spec.fact_ids if fact_id in set(linked)], (
                    label
                )

                supported = True
                for claim in section.claims:
                    if claim.style == "heading":
                        assert supported, f"{label}: heading with no evidence under it"
                        supported = False
                    elif claim.style not in STRUCTURAL_STYLES:
                        supported = True
                assert supported, f"{label}: trailing heading with no evidence under it"


def _role_block_claims(section) -> list[list]:
    """Evidence claims grouped under the heading that opens each role block."""
    blocks: list[list] = []
    for claim in section.claims:
        if claim.style == "heading":
            blocks.append([])
        elif claim.style not in STRUCTURAL_STYLES and blocks:
            blocks[-1].append(claim)
    return blocks


def _pool_blocks(spec, fact_store) -> list[list[str]]:
    """The candidate facts each role block in a section pool could draw on."""
    blocks: list[list[str]] = []
    for fact_id in spec.fact_ids:
        fact = fact_store.get(fact_id)
        if "historical-title" in fact.tags:
            blocks.append([])
        elif blocks and fact.resume_style not in STRUCTURAL_STYLES:
            blocks[-1].append(fact_id)
    return blocks


def test_every_role_block_reaches_its_floor(
    profile_store: ProfileStore, fact_store, draft_factory
) -> None:
    """A long role must not be reduced to a line or two by section-wide ranking.

    Before role-block floors, one section budget was handed out purely by rank,
    so a Team Leader role of four and a half years could reach the page with two
    bullets while an older role took seven. A floor is a floor for every Profile
    and Emphasis, not only the one the complaint came from.
    """
    for profile in profile_store.profiles.values():
        for spec in profile.sections:
            if not spec.min_claims_per_role and not spec.min_quantitative_per_role:
                continue
            for emphasis in profile.allowed_emphases:
                setup = draft_factory(
                    ACCOUNT_MANAGER_JOB,
                    profile_override=profile.profile.value,
                    track_override=profile.track.value,
                    emphasis_override=emphasis.value,
                )
                section = next(item for item in setup.draft.sections if item.name == spec.name_en)
                pools = _pool_blocks(spec, fact_store)
                for index, block in enumerate(_role_block_claims(section)):
                    label = f"{profile.profile.value}/{emphasis.value}/{spec.name_en}/block{index}"
                    # A floor cannot conjure evidence: a block whose pool is
                    # shallower than the floor owes only everything it has.
                    floor = min(spec.min_claims_per_role, len(pools[index]))
                    assert len(block) >= floor, label


def test_payme_tech_sales_selection_uses_job_evidence_and_business_presentations(
    draft_factory,
) -> None:
    setup = draft_factory(
        PAYME_TECH_SALES_JOB,
        track_override="tech-sales",
        profile_override="tech-sales",
        emphasis_override="new-business",
    )
    draft = setup.draft

    assert setup.analysis.fit.value == "medium"
    # `sales.cycle.closing` is deliberately absent: five lines per role is the
    # ceiling, and closing evidence already reaches the page through the merged
    # negotiation/tenders bullet and the leadership block. Outreach has no such
    # substitute, and the posting asks for phone and email engagement by name.
    assert {
        "sales.cycle.outreach",
        "sales.cycle.prospecting",
        "sales.leadership.pipeline",
        "sales.metric.new_customers",
        "sales.achievement.complex_deals",
        "development.phdigital.crm",
    } <= set(draft.selected_fact_ids)

    sections = {section.name: section for section in draft.sections}
    summary = sections["Professional Summary"].claims
    assert len(summary) == 1
    assert summary[0].claim_type == "composite"
    assert summary[0].template_id == "tech-sales.summary.new-business-tenure"
    assert "prospecting, needs discovery, negotiation, closing" in summary[0].text
    # The tenure is a canonical fact linked to the claim, never a number the
    # wording asserts on its own.
    assert "sales.summary.tenure" in summary[0].fact_ids
    assert "nearly 6 years" in summary[0].text

    technology = sections["Technology Experience"].claims
    technology_text = " ".join(claim.text for claim in technology)
    assert "how software products are designed and delivered" in technology_text
    assert (
        "automated workflows, document generation, and operational status tracking"
        in technology_text
    )
    assert "scheduled jobs" not in technology_text
    assert "retries" not in technology_text
    assert "state-driven business processes" not in technology_text

    # A Tech Sales reader is a technical buyer's counterpart: the stack belongs
    # on the page as searchable terms, but as one line of vocabulary rather than
    # a framework inventory that reads as a developer's CV.
    skills = sections["Sales & Technical Skills"].claims
    skills_text = " ".join(claim.text for claim in skills)
    assert "Priority ERP" in skills_text
    assert "Excel" in skills_text
    assert "REST APIs, Python, FastAPI" in skills_text
    assert "React" in skills_text
    assert "PostgreSQL" in skills_text
    assert len(skills) == 3


def test_the_headline_reads_for_a_recruiter_and_the_filename_does_not(
    profile_store: ProfileStore, draft_factory
) -> None:
    """A headline written for a reader must not become the artifact path.

    `normalized_role` files the CV — the PDF name and the role folder — so a
    headline carrying separators and a positioning statement has to live in its
    own field or it ends up in a filename.
    """
    profile = profile_store.get("tech-sales")
    setup = draft_factory(
        PAYME_TECH_SALES_JOB,
        track_override="tech-sales",
        profile_override="tech-sales",
        emphasis_override="new-business",
    )

    assert setup.draft.headline.text == "Technical Sales | B2B Sales | Software Background"
    assert setup.draft.headline.text in profile.safe_headlines
    assert profile.normalized_role == "Tech Sales"
    assert normalized_role_filename(profile.normalized_role, setup.candidate) == (
        "Matan Malka - Tech Sales - CV.pdf"
    )


# --- M3 Stage F: the posting's requirements rank the evidence ----------------
#
# `requirement_rank` took the slot `gap_substitute` held. No posting in the
# corpus exercises the reordering - every one either extracts no requirements at
# all, or its supporting facts land on structure and uncontended sections - so
# these drive the ordering directly rather than through a job text that cannot
# reach it. `Professional Summary` for `account-manager` is the bed: three
# contenders for one claim, decided by a semantic score of 200 against 20 and 0.


def _requirement(requirement_id: str, *, mandatory: bool, coverage: Coverage, supports: list[str]):
    return Requirement(
        requirement_id=requirement_id,
        text="stated in the posting",
        kind="presence",
        mandatory=mandatory,
        coverage=coverage,
        supporting_fact_ids=supports,
    )


def _summary_selection(
    profile_store, policy_store, fact_store, classify, *, requirements=(), gaps=()
):
    analysis = classify(ACCOUNT_MANAGER_JOB, profile_override="account-manager")
    analysis = analysis.model_copy(update={"requirements": list(requirements), "gaps": list(gaps)})
    selected, manifest = build_selection(
        analysis=analysis,
        profile=profile_store.get("account-manager"),
        policy=policy_store.get(analysis.emphasis),
        policy_store_version=policy_store.version,
        facts=fact_store,
    )
    return selected["Professional Summary"], manifest


@pytest.mark.parametrize("rank", [-1, 3, 99])
def test_a_manifest_cannot_record_a_tier_the_ranking_has_no_meaning_for(rank: int) -> None:
    """The tier is an enumeration, not a score.

    Mandatory, preferred and unasked are the whole vocabulary. A value outside
    them would still sort - above every real tier, or below all of them - while
    describing nothing a reader of the manifest could interpret.
    """
    with pytest.raises(ValidationError):
        SelectionCandidate(
            fact_id="sales.summary.tech",
            section="Professional Summary",
            pool_index=0,
            profile_score=0,
            emphasis_score=0,
            semantic_score=0,
            keyword_hits=0,
            gap_substitute=False,
            requirement_rank=rank,
            outcome="selected",
        )


def test_a_manifest_written_before_the_tier_existed_still_reads() -> None:
    """Policy 1.0.0 wrote no tier, and those manifests are records."""
    candidate = SelectionCandidate(
        fact_id="sales.summary.tech",
        section="Professional Summary",
        pool_index=0,
        profile_score=0,
        emphasis_score=0,
        semantic_score=0,
        keyword_hits=0,
        gap_substitute=True,
        outcome="selected",
    )
    assert candidate.requirement_rank == 0


def test_a_mandatory_requirement_outranks_a_stronger_semantic_score(
    profile_store: ProfileStore, policy_store, fact_store: FactStore, classify
) -> None:
    """What the employer demanded decides before what the Profile prefers.

    `sales.summary.account` takes this section on semantics alone, 200 against
    0. Naming `sales.summary.tech` as evidence for a mandatory requirement has
    to be enough to reverse that, or the authority order is not an authority
    order.
    """
    baseline, _ = _summary_selection(profile_store, policy_store, fact_store, classify)
    assert baseline == ["sales.summary.account"]

    selected, _ = _summary_selection(
        profile_store,
        policy_store,
        fact_store,
        classify,
        requirements=[
            _requirement(
                "r-mand", mandatory=True, coverage="matched", supports=["sales.summary.tech"]
            )
        ],
    )
    assert selected == ["sales.summary.tech"]


def test_evidence_for_a_met_requirement_carries_authority_a_substitute_never_had(
    profile_store: ProfileStore, policy_store, fact_store: FactStore, classify
) -> None:
    """The widening `gap_substitute` could not express.

    A substitute stands in for something the candidate lacks, so under policy
    1.0.0 the only facts with authority in this slot were the ones answering a
    failure. Evidence that a demanded thing is genuinely held ranked level with
    a fact the posting never mentioned - even though it is the better thing to
    put on the page.
    """
    matched = _requirement(
        "r-met", mandatory=True, coverage="matched", supports=["sales.summary.tech"]
    )
    selected, manifest = _summary_selection(
        profile_store, policy_store, fact_store, classify, requirements=[matched]
    )
    assert selected == ["sales.summary.tech"]
    winner = next(c for c in manifest.candidates if c.fact_id == "sales.summary.tech")
    assert (winner.requirement_rank, winner.gap_substitute) == (2, False)


def test_a_mandatory_requirement_outranks_a_preferred_one(
    profile_store: ProfileStore, policy_store, fact_store: FactStore, classify
) -> None:
    """Between two answered asks, the one the employer made a condition wins."""
    selected, _ = _summary_selection(
        profile_store,
        policy_store,
        fact_store,
        classify,
        requirements=[
            _requirement(
                "r-pref", mandatory=False, coverage="matched", supports=["sales.summary.tech"]
            ),
            _requirement(
                "r-mand",
                mandatory=True,
                coverage="matched",
                supports=["sales.summary.new_business"],
            ),
        ],
    )
    assert selected == ["sales.summary.new_business"]


def test_a_gap_takes_the_necessity_of_the_requirement_it_projects(
    profile_store: ProfileStore, policy_store, fact_store: FactStore, classify
) -> None:
    """A substitute is ranked by what it stands in for, not by being a substitute."""
    requirements = [
        _requirement("r-mand", mandatory=True, coverage="unsupported", supports=[]),
        _requirement("r-pref", mandatory=False, coverage="unsupported", supports=[]),
    ]
    gaps = [
        Gap(
            requirement="preferred ask",
            severity="warning",
            reason="not held",
            substitute_fact_ids=["sales.summary.account"],
            requirement_id="r-pref",
        ),
        Gap(
            requirement="mandatory ask",
            severity="hard",
            reason="not held",
            substitute_fact_ids=["sales.summary.tech"],
            requirement_id="r-mand",
        ),
    ]
    selected, _ = _summary_selection(
        profile_store, policy_store, fact_store, classify, requirements=requirements, gaps=gaps
    )
    # `sales.summary.account` substitutes too, and outscores the winner 200 to 0.
    assert selected == ["sales.summary.tech"]


def test_an_analysis_without_requirements_ranks_as_policy_1_0_0_did(
    profile_store: ProfileStore, policy_store, fact_store: FactStore, classify
) -> None:
    """Gaps from before requirement extraction stay on one tier.

    Such an analysis has no requirements, so nothing reaches the mandatory tier
    and every substitute sits together above every non-substitute - which is
    exactly `int(gap_substitute)`. Splitting them by severity here would rerank
    stored analyses the rework promised to leave alone.
    """
    gaps = [
        Gap(
            requirement="hard ask",
            severity="hard",
            reason="not held",
            substitute_fact_ids=["sales.summary.tech"],
        ),
        Gap(
            requirement="soft ask",
            severity="warning",
            reason="not held",
            substitute_fact_ids=["sales.summary.new_business"],
        ),
    ]
    selected, manifest = _summary_selection(
        profile_store, policy_store, fact_store, classify, gaps=gaps
    )
    # Both substitute, so severity must not separate them: the semantic score
    # decides, 20 against 0, exactly as it did under `int(gap_substitute)`.
    assert selected == ["sales.summary.new_business"]
    tiers = {
        candidate.fact_id: candidate.requirement_rank
        for candidate in manifest.candidates
        if candidate.section == "Professional Summary"
    }
    assert tiers == {
        "sales.summary.account": 0,
        "sales.summary.new_business": 1,
        "sales.summary.tech": 1,
    }


# --- M3 Stage D: one user's pin/exclude overlay -----------------------------
#
# The overlay is what §13's `create_selection_plan` receives. It constrains the
# engine and never replaces it, so every property above still has to hold with
# an overlay applied - and an overlay that cannot hold one of them is refused
# rather than trimmed to fit.


def _account_manager_selection(profile_store, policy_store, fact_store, classify, **overlay):
    analysis = classify(ACCOUNT_MANAGER_JOB, profile_override="account-manager")
    return build_selection(
        analysis=analysis,
        profile=profile_store.get("account-manager"),
        policy=policy_store.get(analysis.emphasis),
        policy_store_version=policy_store.version,
        facts=fact_store,
        **overlay,
    )


def test_selected_fact_without_target_language_rendering_is_refused_before_drafting(
    profile_store: ProfileStore, policy_store, fact_store: FactStore, classify
) -> None:
    analysis = classify(ACCOUNT_MANAGER_JOB, profile_override="account-manager")
    _sections, baseline = build_selection(
        analysis=analysis,
        profile=profile_store.get("account-manager"),
        policy=policy_store.get(analysis.emphasis),
        policy_store_version=policy_store.version,
        facts=fact_store,
    )
    missing_id = baseline.selected_fact_ids[0]
    bilingual = {
        fact_id: fact.model_copy(
            update={
                "renderings": (
                    {key: value for key, value in fact.renderings.items() if key != "he"}
                    if fact_id == missing_id
                    else {**fact.renderings, "he": fact.renderings["en"]}
                )
            }
        )
        for fact_id, fact in fact_store.facts.items()
    }

    with pytest.raises(MissingFactRendering) as raised:
        build_selection(
            analysis=analysis.model_copy(update={"language": "he"}),
            profile=profile_store.get("account-manager"),
            policy=policy_store.get(analysis.emphasis),
            policy_store_version=policy_store.version,
            facts=FactStore(bilingual, fact_store.source_versions),
        )

    assert raised.value.fact_id == missing_id
    assert raised.value.language == "he"
    assert str(raised.value) == f"fact {missing_id} has no 'he' rendering"


def test_an_overlay_free_build_is_byte_for_byte_the_build_that_ran_before(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """The default path is the old path.

    Both parameters default to empty, and nothing about the algorithm may depend
    on their existence. Every stored SelectionPlan and every golden output was
    produced without them, so a difference here would be a silent rewrite of
    records that are supposed to be immutable.
    """
    selected, manifest = _account_manager_selection(
        profile_store, policy_store, fact_store, classify
    )
    with_empty, manifest_empty = _account_manager_selection(
        profile_store,
        policy_store,
        fact_store,
        classify,
        pinned_fact_ids=frozenset(),
        excluded_fact_ids=frozenset(),
    )

    assert with_empty == selected
    assert manifest_empty == manifest


def test_a_pinned_fact_survives_the_budget_that_had_omitted_it(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """Explicit inclusion is a hold, which is the only way to say it."""
    _, before = _account_manager_selection(profile_store, policy_store, fact_store, classify)
    omitted = next(
        candidate
        for candidate in before.candidates
        if candidate.section == "Core Skills" and candidate.outcome == "omitted"
    )

    selected, after = _account_manager_selection(
        profile_store,
        policy_store,
        fact_store,
        classify,
        pinned_fact_ids=frozenset({omitted.fact_id}),
    )

    outcomes = {candidate.fact_id: candidate for candidate in after.candidates}
    assert outcomes[omitted.fact_id].outcome == "pinned"
    assert omitted.fact_id in after.selected_fact_ids
    assert omitted.fact_id in selected["Core Skills"]
    # The budget did not grow to accommodate it: something it outranked left.
    assert len(selected["Core Skills"]) == len(
        [
            candidate
            for candidate in before.candidates
            if candidate.section == "Core Skills" and candidate.outcome != "omitted"
        ]
    )


def test_an_excluded_fact_leaves_the_document_and_the_manifest_says_who_removed_it(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """A fact the engine ranked out and one the user removed are different facts.

    Both are absent from the document, and only the candidate accounting can
    still tell them apart, which is what makes the plan evidence of a decision
    rather than of an outcome.
    """
    _, before = _account_manager_selection(profile_store, policy_store, fact_store, classify)
    chosen = next(
        candidate
        for candidate in before.candidates
        if candidate.section == "Core Skills" and candidate.outcome == "selected"
    )

    selected, after = _account_manager_selection(
        profile_store,
        policy_store,
        fact_store,
        classify,
        excluded_fact_ids=frozenset({chosen.fact_id}),
    )

    outcomes = {candidate.fact_id: candidate for candidate in after.candidates}
    assert outcomes[chosen.fact_id].outcome == "omitted"
    assert outcomes[chosen.fact_id].reason == "excluded_by_user"
    assert chosen.fact_id not in after.selected_fact_ids
    assert chosen.fact_id not in selected["Core Skills"]
    # Still accounted for. Dropping it from the manifest would leave no record
    # that the fact was ever a candidate.
    assert chosen.fact_id in {candidate.fact_id for candidate in after.candidates}
    # The section refilled from its own pool rather than shrinking.
    assert len(selected["Core Skills"]) == len(
        [
            candidate
            for candidate in before.candidates
            if candidate.section == "Core Skills" and candidate.outcome != "omitted"
        ]
    )


def test_an_overlay_naming_a_fact_the_profile_never_offered_is_refused(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    with pytest.raises(SelectionError, match="offers no candidate named"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            classify,
            pinned_fact_ids=frozenset({"development.stack.python"}),
        )


def test_a_fact_named_on_both_sides_of_the_overlay_is_refused(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """Neither reading is safe, so neither is chosen."""
    with pytest.raises(SelectionError, match="pinned and excluded"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            classify,
            pinned_fact_ids=frozenset({"sales.achievement.retention"}),
            excluded_fact_ids=frozenset({"sales.achievement.retention"}),
        )


def test_structure_cannot_be_excluded_as_if_it_were_evidence(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """Removing a heading does not shorten a CV; it orphans what is under it."""
    for fact_id in ("sales.role.leader.title", "sales.role.leader.dates"):
        with pytest.raises(SelectionError, match="structure, not evidence"):
            _account_manager_selection(
                profile_store,
                policy_store,
                fact_store,
                classify,
                excluded_fact_ids=frozenset({fact_id}),
            )


def test_an_exclusion_that_costs_a_role_block_its_quantitative_floor_is_refused(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """The invariant is not traded for the user's choice, and neither is dropped.

    `sales.metric.new_customers` is the only verified-quantitative claim under
    the field-sales role. Honouring the exclusion silently would leave that role
    described in duties alone, which is exactly the shape
    `min_quantitative_per_role` exists to prevent.
    """
    with pytest.raises(SelectionError, match="cannot reach its floors without"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            classify,
            excluded_fact_ids=frozenset({"sales.metric.new_customers"}),
        )


def test_an_exclusion_that_empties_a_required_tag_is_refused(
    profile_store: ProfileStore, policy_store, fact_store, classify
) -> None:
    """The rescue refills a required tag from the pool; it cannot refill nothing.

    An Account Manager CV that can evidence no account management is not that
    Profile, whatever the user asked for, so the command is refused and names
    the exclusions that caused it.
    """
    profile = profile_store.get("account-manager")
    assert profile.required_tags == ["account-management"]
    carriers = frozenset(
        {
            "sales.summary.account",
            "sales.metric.recurring_customers",
            "sales.cycle.account_management",
        }
    )

    with pytest.raises(SelectionError, match="'account-management' would be left uncovered"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            classify,
            excluded_fact_ids=carriers,
        )


def test_acceptance_is_not_an_input_to_selection(
    profile_store, policy_store, fact_store, classify
) -> None:
    """Proceeding past a gap is a decision about the gap, not about the facts.

    `build_selection` is never given the acceptances, so an accepted gap cannot
    move a fact up or down the ranking. Asserted on the signature rather than
    on one output, because a future caller could otherwise thread them in
    without any test noticing.
    """
    import inspect

    parameters = set(inspect.signature(build_selection).parameters)
    assert not parameters & {"accepted_gaps", "accepted_requirement_ids"}
