from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path

from fixtures.knowledge import SOURCE_ROOT
from seed import V2_IDENTITY_FACT, facts_in, source_texts

from cv_engine.domain.contracts.knowledge import FactStatus
from cv_engine.domain.facts import FactStore
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


def _assert_refused(label: str, documents: dict, store: FactStore, message: str) -> None:
    try:
        ProfileStore.from_documents(documents, store)
    except ProfileStoreError as error:
        assert re.search(message, str(error)), (label, str(error))
    else:
        raise AssertionError(f"{label}: accepted")


def _profile(documents: dict, name: str) -> str:
    return next(key for key in documents if key.endswith(f"{name}.yaml"))


def test_dated_role_coverage(fact_store, profile_store, project_root: Path) -> None:
    """No Profile drops a dated role without saying so, and no declaration excuses a lie.

    The two Profiles absent from `DECLARED_ROLE_OMISSIONS` carry all three roles,
    so between them the ten Profiles account for every dated role in the store.

    Only canonical roles are owed an account: a role still moving through
    `pending -> confirmed -> canonical` is not a fact a CV may be built from, so
    requiring every Profile to carry or decline it would wedge the profile set.

    Refused: dropping a role with no waiver; a waiver naming something that is not
    a dated canonical role, or a role the Profile carries anyway; a waiver without
    a reason, which leaves the omission as unexplained as never declaring it; and
    a hole between two carried roles. Truncating either end of the history states
    nothing about the months outside it, but dropping the role *between* two the
    CV prints leaves them abutting, which their own dates deny - so declaring that
    omission does not make it allowed.
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

    def dropped(documents: dict) -> None:
        documents[_profile(documents, "account-executive")].pop("omitted_roles")

    def stale(documents: dict) -> None:
        documents[_profile(documents, "account-executive")]["omitted_roles"][
            "sales.summary.tech"
        ] = "not a role"

    def contradictory(documents: dict) -> None:
        documents[_profile(documents, "tech-sales")]["omitted_roles"] = {
            "development.phdigital.role": "carried too"
        }

    def hole(documents: dict) -> None:
        target = _profile(documents, "tech-sales")
        for section in documents[target]["sections"]:
            for key in ("fact_ids", "pinned_fact_ids"):
                section[key] = [
                    fact_id
                    for fact_id in section.get(key, [])
                    if fact_id != "sales.role.leader.title"
                ]
        documents[target]["omitted_roles"] = {
            "sales.role.leader.title": "declared, and still refused"
        }

    def reasonless(documents: dict) -> None:
        documents[_profile(documents, "account-executive")]["omitted_roles"][
            "development.phdigital.role"
        ] = "   "

    for mutate, message in (
        (dropped, "neither offers nor waives"),
        (stale, "not a dated canonical role"),
        (contradictory, "both offers and waives"),
        (hole, "unexplained gap"),
        (reasonless, "omitted roles need a reason"),
    ):
        documents = profile_documents(project_root)
        mutate(documents)
        _assert_refused(mutate.__name__, documents, fact_store, message)


def test_a_role_title_is_a_dated_heading_with_a_real_forward_span(
    fact_store, project_root: Path
) -> None:
    """Coverage only proves a role is offered; its span and heading are what carry it.

    A numeric shape is not yet a date range: each bad span parses under a bare
    `\\d{2}` reading and yields an ordinal the gap sweep would compare in good
    faith, so a nonsense span could decide a timeline is continuous. Losing the
    dates must not be a way out of the coverage rule either.

    Selection treats a heading as structure and keeps it unconditionally, so
    offering a role is enough only while the role is one. Styled as evidence it
    is scored, competes for the section budget, and can be dropped below it -
    passing the coverage rule and still vanishing from the page. `bullet`,
    `paragraph` and `item` are the styles that would actually be dropped;
    `date` and `contact` survive selection but are not a title either.
    """
    cases: list[tuple[dict, str]] = [
        ({"effective_dates": "2025-00/2025-06"}, "no readable span"),
        ({"effective_dates": "2025-13/2026-01"}, "no readable span"),
        ({"effective_dates": "2026-06/2025-02"}, "ends before it starts"),
        ({"effective_dates": None}, "no readable span"),
    ]
    for style in ("bullet", "paragraph", "item", "date", "contact"):
        assert style in {"date", "contact"} or style not in STRUCTURAL_STYLES
        cases.append(({"resume_style": style}, "not 'heading'"))

    documents = profile_documents(project_root)
    for update, message in cases:
        facts = dict(fact_store.facts)
        facts["sales.role.field.title"] = facts["sales.role.field.title"].model_copy(update=update)
        store = FactStore(facts, fact_store.source_versions)
        _assert_refused(repr(update), copy.deepcopy(documents), store, message)


def test_seed_and_repository_knowledge_hold_the_same_facts() -> None:
    """The frozen test seed must not drift from the candidate's live facts.

    The seed is a second copy of `base/*.json`, kept frozen so that editing a real
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
