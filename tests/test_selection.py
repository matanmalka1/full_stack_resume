"""Selection must actually select.

Every test here guards a property that was silently false before selection
existed: Profiles listed the facts that would be printed, so Emphasis, job text,
keywords and gaps could not change a single line of the document.
"""

from __future__ import annotations

import pytest
from helpers import PAYME_TECH_SALES_JOB

from cv_engine.domain.draft_markdown import serialize_markdown
from cv_engine.domain.models import Emphasis, Profile
from cv_engine.domain.profiles import ProfileStore
from cv_engine.domain.selection import STRUCTURAL_STYLES, SelectionError, build_selection
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
    profile_store: ProfileStore, policy_store, fact_store
) -> None:
    """A Profile invariant outranks the Emphasis that would have dropped it."""
    from cv_engine.domain.analysis.classification import classify_job

    base = profile_store.get("account-manager")
    profile = Profile.model_validate(
        {
            **base.model_dump(mode="json"),
            "required_tags": ["retention"],
        }
    )
    analysis = classify_job(
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


# --- M3 Stage D: one user's pin/exclude overlay -----------------------------
#
# The overlay is what §13's `create_selection_plan` receives. It constrains the
# engine and never replaces it, so every property above still has to hold with
# an overlay applied - and an overlay that cannot hold one of them is refused
# rather than trimmed to fit.


def _account_manager_selection(profile_store, policy_store, fact_store, **overlay):
    from cv_engine.domain.analysis.classification import classify_job

    analysis = classify_job(ACCOUNT_MANAGER_JOB, profile_override="account-manager")
    return build_selection(
        analysis=analysis,
        profile=profile_store.get("account-manager"),
        policy=policy_store.get(analysis.emphasis),
        policy_store_version=policy_store.version,
        facts=fact_store,
        **overlay,
    )


def test_an_overlay_free_build_is_byte_for_byte_the_build_that_ran_before(
    profile_store: ProfileStore, policy_store, fact_store
) -> None:
    """The default path is the old path.

    Both parameters default to empty, and nothing about the algorithm may depend
    on their existence. Every stored SelectionPlan and every golden output was
    produced without them, so a difference here would be a silent rewrite of
    records that are supposed to be immutable.
    """
    selected, manifest = _account_manager_selection(profile_store, policy_store, fact_store)
    with_empty, manifest_empty = _account_manager_selection(
        profile_store,
        policy_store,
        fact_store,
        pinned_fact_ids=frozenset(),
        excluded_fact_ids=frozenset(),
    )

    assert with_empty == selected
    assert manifest_empty == manifest


def test_a_pinned_fact_survives_the_budget_that_had_omitted_it(
    profile_store: ProfileStore, policy_store, fact_store
) -> None:
    """Explicit inclusion is a hold, which is the only way to say it."""
    _, before = _account_manager_selection(profile_store, policy_store, fact_store)
    omitted = next(
        candidate
        for candidate in before.candidates
        if candidate.section == "Core Skills" and candidate.outcome == "omitted"
    )

    selected, after = _account_manager_selection(
        profile_store,
        policy_store,
        fact_store,
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
    profile_store: ProfileStore, policy_store, fact_store
) -> None:
    """A fact the engine ranked out and one the user removed are different facts.

    Both are absent from the document, and only the candidate accounting can
    still tell them apart, which is what makes the plan evidence of a decision
    rather than of an outcome.
    """
    _, before = _account_manager_selection(profile_store, policy_store, fact_store)
    chosen = next(
        candidate
        for candidate in before.candidates
        if candidate.section == "Core Skills" and candidate.outcome == "selected"
    )

    selected, after = _account_manager_selection(
        profile_store,
        policy_store,
        fact_store,
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
    profile_store: ProfileStore, policy_store, fact_store
) -> None:
    with pytest.raises(SelectionError, match="offers no candidate named"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            pinned_fact_ids=frozenset({"development.stack.python"}),
        )


def test_a_fact_named_on_both_sides_of_the_overlay_is_refused(
    profile_store: ProfileStore, policy_store, fact_store
) -> None:
    """Neither reading is safe, so neither is chosen."""
    with pytest.raises(SelectionError, match="pinned and excluded"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            pinned_fact_ids=frozenset({"sales.achievement.retention"}),
            excluded_fact_ids=frozenset({"sales.achievement.retention"}),
        )


@pytest.mark.parametrize(
    "fact_id",
    ["sales.role.leader.title", "sales.role.leader.dates"],
    ids=["role-title", "role-dates"],
)
def test_structure_cannot_be_excluded_as_if_it_were_evidence(
    profile_store: ProfileStore, policy_store, fact_store, fact_id: str
) -> None:
    """Removing a heading does not shorten a CV; it orphans what is under it."""
    with pytest.raises(SelectionError, match="structure, not evidence"):
        _account_manager_selection(
            profile_store,
            policy_store,
            fact_store,
            excluded_fact_ids=frozenset({fact_id}),
        )


def test_an_exclusion_that_costs_a_role_block_its_quantitative_floor_is_refused(
    profile_store: ProfileStore, policy_store, fact_store
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
            excluded_fact_ids=frozenset({"sales.metric.new_customers"}),
        )


def test_an_exclusion_that_empties_a_required_tag_is_refused(
    profile_store: ProfileStore, policy_store, fact_store
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
            excluded_fact_ids=carriers,
        )
