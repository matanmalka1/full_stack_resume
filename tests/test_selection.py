"""Selection must actually select.

Every test here guards a property that was silently false before selection
existed: Profiles listed the facts that would be printed, so Emphasis, job text,
keywords and gaps could not change a single line of the document.
"""

from __future__ import annotations

from pathlib import Path

from cv_engine.drafts import serialize_markdown
from cv_engine.models import Emphasis, Profile
from cv_engine.profiles import ProfileStore
from cv_engine.rendering import normalized_role_filename, render_html
from cv_engine.selection import STRUCTURAL_STYLES, build_selection

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
        for emphasis in ("account-growth", "new-business", "balanced-sales", "tech-consultative-sales")
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
    from cv_engine.analysis import classify_job

    base = profile_store.get("account-manager")
    profile = Profile.model_validate({
        **base.model_dump(mode="json"),
        "required_tags": ["retention"],
    })
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
        candidate.fact_id for candidate in manifest.candidates
        if candidate.reason == "evicted_by_required_tag_rescue"
    ]
    assert evicted == ["sales.achievement.complex_deals"]
    assert manifest.required_tag_coverage["retention"] == ["sales.achievement.retention"]


def test_the_widest_profile_still_fits_its_page_allowance(
    v1_repo: Path, tmp_path: Path, profile_store: ProfileStore, draft_factory, render_validator
) -> None:
    """A raised section budget must not push the CV past its page allowance.

    Sales Management carries the largest Work Experience budget in the repo — it
    was raised so an account-growth Emphasis could still evidence account work —
    so it is the profile that would overflow first.
    """
    profile = profile_store.get("sales-management")
    assert profile.allow_two_pages
    setup = draft_factory(
        "Sales team leader managing a B2B account portfolio, coaching, forecasting and growth",
        profile_override="sales-management",
        track_override="sales",
        emphasis_override="account-growth",
    )

    target = tmp_path / "sales-management"
    target.mkdir()
    html = render_html(setup.draft, v1_repo, target / "resume.html")
    _geometry, report = render_validator(
        setup.draft,
        profile,
        html,
        target / normalized_role_filename(profile.normalized_role),
        target / "visual.png",
    )

    assert report.passed, report.model_dump()
    assert report.evidence["page_count"] <= 2


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
                assert linked == [fact_id for fact_id in spec.fact_ids if fact_id in set(linked)], label

                supported = True
                for claim in section.claims:
                    if claim.style == "heading":
                        assert supported, f"{label}: heading with no evidence under it"
                        supported = False
                    elif claim.style not in STRUCTURAL_STYLES:
                        supported = True
                assert supported, f"{label}: trailing heading with no evidence under it"
