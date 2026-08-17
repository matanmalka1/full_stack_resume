from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.facts import FactStore, FactStoreError
from cv_engine.models import FactStatus


def test_canonical_fact_store_has_unique_stable_ids(fact_store) -> None:
    facts = fact_store
    # 86 migrated v1 facts plus the v2 candidate identity fact.
    assert len(facts.facts) == 87
    identity = facts.get("common.identity.name", canonical_only=True)
    assert identity.renderings == {"en": "Matan Malka", "he": "מתן מלכה"}
    assert facts.get("sales.metric.team_size").renderings["en"] == "Managed a team of 2-3 sales representatives."
    assert "YoY" not in facts.get("sales.metric.performance").renderings["en"]
    assert facts.get("sales.role.leader.dates").effective_dates == "2020-08/2025-01"
    assert len(facts.version) == 64


def test_duplicate_fact_id_is_rejected(v1_repo: Path) -> None:
    common = v1_repo / "base/common.md"
    payload = json.loads(common.read_text(encoding="utf-8").split("```json\n", 1)[1].split("\n```", 1)[0])
    payload["facts"].append(payload["facts"][0])
    common.write_text("# duplicate\n\n```json\n" + json.dumps(payload) + "\n```\n", encoding="utf-8")
    with pytest.raises(FactStoreError, match="duplicate fact_id"):
        FactStore.load(v1_repo / "base")


def test_fact_lifecycle_requires_confirmation(fact_store) -> None:
    store = fact_store
    fact = store.get("situational.testing")
    store.facts[fact.fact_id] = fact.model_copy(update={"status": FactStatus.PENDING})
    with pytest.raises(FactStoreError, match="explicit confirmation"):
        store.promote(fact.fact_id, FactStatus.CONFIRMED, explicitly_confirmed=False)
    confirmed = store.promote(fact.fact_id, FactStatus.CONFIRMED, explicitly_confirmed=True)
    assert confirmed.status is FactStatus.CONFIRMED
    canonical = store.promote(fact.fact_id, FactStatus.CANONICAL, explicitly_confirmed=True)
    assert canonical.status is FactStatus.CANONICAL


def test_all_required_profiles_reference_existing_facts(fact_store, profile_store) -> None:
    facts = fact_store
    profiles = profile_store
    assert len(profiles.profiles) == 10
    assert profiles.get("tech-sales").track.value == "tech-sales"
    assert profiles.get("sales-management").default_emphasis.value == "leadership"
    assert profiles.get("sales-management").allow_two_pages is True
    assert profiles.get("account-manager").allow_two_pages is False
