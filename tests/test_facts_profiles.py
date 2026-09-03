from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

import pytest
from conftest import SOURCE_ROOT
from seed import V2_IDENTITY_FACT, facts_in, source_texts

from cv_engine.domain.facts import FactStore
from cv_engine.domain.models import FactStatus
from cv_engine.domain.profiles import ProfileStore, ProfileStoreError
from cv_engine.domain.selection import STRUCTURAL_STYLES


def test_canonical_fact_store_has_unique_stable_ids(fact_store) -> None:
    facts = fact_store
    # 96 migrated v1 facts plus the v2 candidate identity fact. 87 -> 93 when the
    # v1 content branch merged in (three development summary restatements, three
    # mm-backend-core facts); 93 -> 97 with the four AI-assisted engineering
    # facts carried over from the v1 worktree.
    assert len(facts.facts) == 97
    # Migrated facts keep their v1 semantic IDs; a fact created for v2 takes
    # UUIDv4 technical identity.
    uuid.UUID(V2_IDENTITY_FACT["fact_id"])
    identity = facts.get(V2_IDENTITY_FACT["fact_id"], canonical_only=True)
    assert identity.renderings == {"en": "Matan Malka", "he": "מתן מלכה"}
    assert (
        facts.get("sales.metric.team_size").renderings["en"]
        == "Managed a team of 2-3 sales representatives."
    )
    assert "YoY" not in facts.get("sales.metric.performance").renderings["en"]
    assert (
        facts.get("situational.agentic_multi_agent")
        .renderings["he"]
        .startswith("תכנן והפעיל תהליך פיתוח רב־סוכנים")
    )
    assert facts.get("sales.role.leader.dates").effective_dates == "2020-08/2025-01"
    assert len(facts.version) == 64


def test_all_required_profiles_reference_existing_facts(fact_store, profile_store) -> None:
    profiles = profile_store
    assert len(profiles.profiles) == 10
    assert profiles.get("tech-sales").track.value == "tech-sales"
    assert profiles.get("sales-management").default_emphasis.value == "leadership"
    assert profiles.get("sales-management").allow_two_pages is True
    assert profiles.get("account-manager").allow_two_pages is False


#: Every dated role a Profile declines to carry, against the Profile that
#: declines it. This is the whole set of deliberate omissions in the repository:
#: `from_documents` derives the requirement from the fact store, so a role added
#: there tomorrow fails every Profile until each one is decided about, and a
#: waiver left behind after a role is retired fails too.
DECLARED_ROLE_OMISSIONS = {
    "account-executive": ["development.phdigital.role"],
    "account-manager": ["development.phdigital.role"],
    "business-development": ["development.phdigital.role"],
    "development": ["sales.role.field.title"],
    "field-sales": ["development.phdigital.role"],
    "key-account-manager": ["development.phdigital.role"],
    "sales-management": ["development.phdigital.role"],
    "sdr-bdr": ["development.phdigital.role"],
}


def profile_documents(project_root: Path) -> dict[str, dict]:
    return {
        str(path): json.loads(path.read_text("utf-8"))
        for path in sorted((project_root / "profiles").glob("**/*.yaml"))
    }


def test_every_dated_role_is_carried_or_declined(fact_store, profile_store) -> None:
    """No Profile drops a dated role without saying so.

    The two Profiles absent from `DECLARED_ROLE_OMISSIONS` carry all three roles,
    so between them the ten Profiles account for every dated role in the store.
    """
    dated = {
        fact.fact_id
        for fact in fact_store.facts.values()
        # Canonical, because that is the surface a CV may be built from and the
        # set `from_documents` derives the requirement over. Counting a pending
        # role here would fail this guard while production stayed correct.
        if fact.status is FactStatus.CANONICAL
        and "historical-title" in fact.tags
        and fact.effective_dates
    }
    assert dated == {
        "development.phdigital.role",
        "sales.role.field.title",
        "sales.role.leader.title",
    }
    declared = {}
    for name, profile in profile_store.profiles.items():
        offered = {
            fact_id for spec in profile.sections for fact_id in spec.fact_ids if fact_id in dated
        }
        assert offered | set(profile.omitted_roles) == dated, name
        if profile.omitted_roles:
            declared[str(name)] = sorted(profile.omitted_roles)
        for reason in profile.omitted_roles.values():
            assert reason.strip(), name
    assert declared == DECLARED_ROLE_OMISSIONS


def test_a_dated_role_cannot_be_dropped_silently(fact_store, project_root: Path) -> None:
    documents = profile_documents(project_root)
    target = next(key for key in documents if key.endswith("account-executive.yaml"))
    documents[target].pop("omitted_roles")
    with pytest.raises(ProfileStoreError, match="neither offers nor waives"):
        ProfileStore.from_documents(documents, fact_store)


def test_a_waiver_must_name_a_dated_role_the_profile_does_not_carry(
    fact_store, project_root: Path
) -> None:
    documents = profile_documents(project_root)
    account_executive = next(key for key in documents if key.endswith("account-executive.yaml"))
    tech_sales = next(key for key in documents if key.endswith("tech-sales.yaml"))

    stale = copy.deepcopy(documents)
    stale[account_executive]["omitted_roles"]["sales.summary.tech"] = "not a role"
    with pytest.raises(ProfileStoreError, match="not a dated canonical role"):
        ProfileStore.from_documents(stale, fact_store)

    contradictory = copy.deepcopy(documents)
    contradictory[tech_sales]["omitted_roles"] = {"development.phdigital.role": "carried too"}
    with pytest.raises(ProfileStoreError, match="both offers and waives"):
        ProfileStore.from_documents(contradictory, fact_store)


def test_no_waiver_clears_a_hole_between_two_carried_roles(fact_store, project_root: Path) -> None:
    """The one omission the printed page misrepresents is refused outright.

    Truncating either end of the history states nothing about the months outside
    it. Dropping the role *between* two the CV prints leaves them abutting, which
    their own dates deny - so declaring the omission does not make it allowed.
    """
    documents = profile_documents(project_root)
    target = next(key for key in documents if key.endswith("tech-sales.yaml"))
    for section in documents[target]["sections"]:
        for key in ("fact_ids", "pinned_fact_ids"):
            section[key] = [
                fact_id for fact_id in section.get(key, []) if fact_id != "sales.role.leader.title"
            ]
    documents[target]["omitted_roles"] = {"sales.role.leader.title": "declared, and still refused"}
    with pytest.raises(ProfileStoreError, match="unexplained gap"):
        ProfileStore.from_documents(documents, fact_store)


def test_a_pending_role_is_not_yet_the_history_a_profile_owes(
    fact_store, project_root: Path
) -> None:
    """Only canonical roles are owed an account.

    A role still moving through `pending -> confirmed -> canonical` is not a
    fact a CV may be built from, so requiring every Profile to carry or decline
    it would make creating one wedge the whole profile set.
    """
    facts = dict(fact_store.facts)
    proposed = facts["sales.role.field.title"].model_copy(
        update={"fact_id": "sales.role.proposed.title", "status": FactStatus.PENDING}
    )
    facts[proposed.fact_id] = proposed
    store = FactStore(facts, fact_store.source_versions)
    profiles = ProfileStore.from_documents(profile_documents(project_root), store)
    assert proposed.fact_id not in {
        fact_id for profile in profiles.profiles.values() for fact_id in profile.omitted_roles
    }


@pytest.mark.parametrize(
    ("span", "message"),
    [
        ("2025-00/2025-06", "no readable span"),
        ("2025-13/2026-01", "no readable span"),
        ("2026-06/2025-02", "ends before it starts"),
    ],
)
def test_a_span_must_be_a_real_forward_interval(
    fact_store, project_root: Path, span: str, message: str
) -> None:
    """A numeric shape is not yet a date range.

    Each of these parses under a bare `\\d{2}` reading and yields an ordinal the
    gap sweep would compare in good faith, so a nonsense span could decide a
    timeline is continuous.
    """
    facts = dict(fact_store.facts)
    facts["sales.role.field.title"] = facts["sales.role.field.title"].model_copy(
        update={"effective_dates": span}
    )
    store = FactStore(facts, fact_store.source_versions)
    with pytest.raises(ProfileStoreError, match=message):
        ProfileStore.from_documents(profile_documents(project_root), store)


@pytest.mark.parametrize("style", ["bullet", "paragraph", "item", "date", "contact"])
def test_a_role_title_must_be_styled_as_a_heading(
    fact_store, project_root: Path, style: str
) -> None:
    """Coverage only proves a role is offered; the heading is what carries it.

    Selection treats a heading as structure and keeps it unconditionally, so
    offering a role is enough only while the role is one. Styled as evidence it
    is scored, competes for the section budget, and can be dropped below it -
    passing this coverage rule and still vanishing from the page. `bullet`,
    `paragraph` and `item` are the styles that would actually be dropped;
    `date` and `contact` survive selection but are not a title either.
    """
    assert style == "date" or style == "contact" or style not in STRUCTURAL_STYLES
    facts = dict(fact_store.facts)
    facts["sales.role.field.title"] = facts["sales.role.field.title"].model_copy(
        update={"resume_style": style}
    )
    store = FactStore(facts, fact_store.source_versions)
    with pytest.raises(ProfileStoreError, match="not 'heading'"):
        ProfileStore.from_documents(profile_documents(project_root), store)


def test_a_waiver_without_a_reason_is_not_a_decision(fact_store, project_root: Path) -> None:
    """An empty reason leaves the omission as unexplained as never declaring it."""
    documents = profile_documents(project_root)
    target = next(key for key in documents if key.endswith("account-executive.yaml"))
    documents[target]["omitted_roles"]["development.phdigital.role"] = "   "
    with pytest.raises(ProfileStoreError, match="omitted roles need a reason"):
        ProfileStore.from_documents(documents, fact_store)


def test_a_role_without_a_readable_span_is_refused(fact_store, project_root: Path) -> None:
    """Losing the dates must not be a way out of the coverage rule."""
    undated = dict(fact_store.facts)
    undated["sales.role.field.title"] = undated["sales.role.field.title"].model_copy(
        update={"effective_dates": None}
    )
    store = FactStore(undated, fact_store.source_versions)
    with pytest.raises(ProfileStoreError, match="no readable span"):
        ProfileStore.from_documents(profile_documents(project_root), store)


def test_seed_and_repository_knowledge_hold_the_same_facts() -> None:
    """The frozen test seed must not drift from the candidate's live facts.

    The seed is a second copy of `base/*.md`, kept frozen so that editing a real
    CV fact cannot silently change what 200-odd tests assert. A copy nobody
    compares is the one that rots, so this compares it.

    Serialization is excluded on purpose. `source_version` differs because the
    live sources have moved on, `source_file` is filled in by the reader, and
    an absent optional key is not a different value from an explicit null. What
    is compared is what a fact says.
    """
    ignored = {"source_version", "source_file"}
    problems: list[str] = []
    for name, text in source_texts().items():
        seeded = facts_in(text)
        live = facts_in((SOURCE_ROOT / "base" / name).read_text(encoding="utf-8"))
        # The identity fact is added through the lifecycle, so it is expected to
        # be live-only; anything else missing from the seed is real drift.
        live_only = set(live) - set(seeded) - {V2_IDENTITY_FACT["fact_id"]}
        problems += [
            f"{name}: {fact_id} is in base/ but not the seed" for fact_id in sorted(live_only)
        ]
        problems += [
            f"{name}: {fact_id} is in the seed but not base/"
            for fact_id in sorted(set(seeded) - set(live))
        ]
        for fact_id in sorted(set(seeded) & set(live)):
            differing = {
                key
                for key in (set(seeded[fact_id]) | set(live[fact_id])) - ignored
                if seeded[fact_id].get(key) != live[fact_id].get(key)
            }
            if differing:
                problems.append(f"{name}: {fact_id} differs in {sorted(differing)}")
    assert not problems, problems
