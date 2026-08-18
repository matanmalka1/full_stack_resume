from __future__ import annotations

import uuid

from cv_engine.infrastructure.canonical_data import V2_IDENTITY_FACT


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
