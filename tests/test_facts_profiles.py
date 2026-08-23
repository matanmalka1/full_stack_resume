from __future__ import annotations

import uuid

from conftest import SOURCE_ROOT
from seed import V2_IDENTITY_FACT, facts_in, source_texts


def test_canonical_fact_store_has_unique_stable_ids(fact_store) -> None:
    facts = fact_store
    # 86 migrated v1 facts plus the v2 candidate identity fact.
    assert len(facts.facts) == 87
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
    assert facts.get("sales.role.leader.dates").effective_dates == "2020-08/2025-01"
    assert len(facts.version) == 64


def test_all_required_profiles_reference_existing_facts(fact_store, profile_store) -> None:
    profiles = profile_store
    assert len(profiles.profiles) == 10
    assert profiles.get("tech-sales").track.value == "tech-sales"
    assert profiles.get("sales-management").default_emphasis.value == "leadership"
    assert profiles.get("sales-management").allow_two_pages is True
    assert profiles.get("account-manager").allow_two_pages is False


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
