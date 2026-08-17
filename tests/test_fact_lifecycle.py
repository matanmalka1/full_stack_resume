from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.infrastructure.db import connect
from cv_engine.domain.facts import FactStore, FactStoreError
from cv_engine.domain.models import FactStatus
from cv_engine.application.services import WorkflowError
from cv_engine.compat import Engine
from helpers import ACCOUNT_MANAGER_JOB, working_claim as _working_claim


NEW_FACT = {
    "fact_id": "situational.sqlite",
    "meaning": "Used SQLite for local application state in a personal project.",
    "renderings": {"en": "Used SQLite for local application state in a personal project."},
    "tags": ["development", "situational", "databases"],
    "provenance": "candidate wording from the user; not yet verified",
    "resume_style": "bullet",
}


def _reload(engine: Engine) -> FactStore:
    """Read the fact store back from disk, as a later process would."""
    return FactStore.load(engine.root / "base")


def test_new_fact_is_persisted_as_pending_and_cannot_reach_a_cv(engine: Engine) -> None:
    result = engine.add_fact("situational_skills.md", dict(NEW_FACT))

    assert result["fact"]["status"] == "pending"
    stored = _reload(engine).get("situational.sqlite")
    assert stored.status is FactStatus.PENDING
    assert stored.source_file == "base/situational_skills.md"
    with pytest.raises(FactStoreError, match="not canonical"):
        _reload(engine).get("situational.sqlite", canonical_only=True)


def test_pending_fact_does_not_invalidate_drafts_built_from_canonical_facts(engine: Engine) -> None:
    """Staging a fact for one application must not break another's draft.

    `facts.version` identifies the canonical surface a CV may be built from, so
    a `pending` fact changes `lifecycle_version` only.
    """
    before = _reload(engine)
    engine.add_fact("situational_skills.md", dict(NEW_FACT))
    after = _reload(engine)

    assert after.version == before.version
    assert after.lifecycle_version != before.lifecycle_version

    engine.promote_fact("situational.sqlite", "confirmed", explicitly_confirmed=True)
    assert _reload(engine).version == before.version

    engine.promote_fact("situational.sqlite", "canonical", explicitly_confirmed=True)
    assert _reload(engine).version != before.version


def test_promotion_requires_explicit_confirmation_and_a_legal_transition(engine: Engine) -> None:
    engine.add_fact("situational_skills.md", dict(NEW_FACT))

    with pytest.raises(FactStoreError, match="explicit confirmation"):
        engine.promote_fact("situational.sqlite", "confirmed", explicitly_confirmed=False)
    with pytest.raises(FactStoreError, match="invalid fact transition"):
        engine.promote_fact("situational.sqlite", "canonical", explicitly_confirmed=True)
    assert _reload(engine).get("situational.sqlite").status is FactStatus.PENDING


def test_lifecycle_survives_process_boundaries_through_the_cli(cli_runner, v1_repo: Path) -> None:
    added = cli_runner(
        "fact", "add",
        "--source", "situational_skills.md",
        "--fact-id", "situational.sqlite",
        "--meaning", NEW_FACT["meaning"],
        "--en", NEW_FACT["renderings"]["en"],
        "--tag", "development",
        "--tag", "situational",
        "--style", "bullet",
        "--provenance", NEW_FACT["provenance"],
    )
    assert added.returncode == 0, added.stdout + added.stderr
    assert json.loads(added.stdout)["fact"]["status"] == "pending"

    unconfirmed = cli_runner("fact", "confirm", "situational.sqlite")
    assert unconfirmed.returncode == 2
    assert "requires explicit --confirm" in unconfirmed.stderr

    assert cli_runner("fact", "confirm", "situational.sqlite", "--confirm").returncode == 0
    assert cli_runner("fact", "promote", "situational.sqlite", "--confirm").returncode == 0

    listed = cli_runner("fact", "list", "--status", "canonical")
    assert listed.returncode == 0
    ids = [fact["fact_id"] for fact in json.loads(listed.stdout)]
    assert "situational.sqlite" in ids
    assert FactStore.load(v1_repo / "base").get("situational.sqlite").status is FactStatus.CANONICAL

    history = json.loads(cli_runner("fact", "history", "situational.sqlite").stdout)
    assert [(event["from_status"], event["to_status"]) for event in history] == [
        (None, "pending"),
        ("pending", "confirmed"),
        ("confirmed", "canonical"),
    ]


def test_explicit_confirmation_may_create_a_canonical_fact_directly(engine: Engine) -> None:
    result = engine.add_fact("situational_skills.md", dict(NEW_FACT), canonical=True)

    assert result["fact"]["status"] == "canonical"
    assert result["fact"]["confirmed_at"]
    assert _reload(engine).get("situational.sqlite", canonical_only=True)


def test_duplicate_fact_ids_are_refused(engine: Engine) -> None:
    engine.add_fact("situational_skills.md", dict(NEW_FACT))

    with pytest.raises(FactStoreError, match="fact already exists"):
        engine.add_fact("situational_skills.md", dict(NEW_FACT))
    with pytest.raises(FactStoreError, match="fact already exists"):
        engine.add_fact("common.md", {**NEW_FACT, "meaning": "different meaning"})


def test_lifecycle_events_are_immutable(engine: Engine) -> None:
    engine.add_fact("situational_skills.md", dict(NEW_FACT))

    with connect(engine.repo.path) as connection:
        with pytest.raises(Exception, match="immutable record"):
            connection.execute("UPDATE fact_events SET to_status='canonical'")
        with pytest.raises(Exception, match="immutable record"):
            connection.execute("DELETE FROM fact_events")


def test_reconcile_detects_a_status_changed_outside_the_lifecycle(engine: Engine) -> None:
    engine.add_fact("situational_skills.md", dict(NEW_FACT))
    assert engine.reconcile_facts()["passed"]

    source = engine.root / "base/situational_skills.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace('"status": "pending"', '"status": "canonical"'),
        encoding="utf-8",
    )

    report = engine.reconcile_facts()
    assert not report["passed"]
    assert report["problems"] == [
        "fact situational.sqlite is canonical on disk but the lifecycle trail "
        "last recorded pending"
    ]


def test_reconcile_detects_an_untracked_pending_fact(engine: Engine) -> None:
    source = engine.root / "base/situational_skills.md"
    payload = json.loads(source.read_text(encoding="utf-8").split("```json\n", 1)[1].split("\n```", 1)[0])
    payload["facts"].append({**NEW_FACT, "status": "pending", "confirmed_at": None,
                             "effective_dates": None, "replaces": None, "source_file": ""})
    source.write_text(
        "# Situational Canonical Facts\n\n```json\n" + json.dumps(payload) + "\n```\n",
        encoding="utf-8",
    )

    report = engine.reconcile_facts()
    assert not report["passed"]
    assert report["problems"] == ["non-canonical fact has no lifecycle event: situational.sqlite"]


def test_only_canonical_facts_may_enter_a_profile_pool(engine: Engine) -> None:
    engine.add_fact("situational_skills.md", dict(NEW_FACT))

    with pytest.raises(WorkflowError, match="only canonical facts"):
        engine.attach_fact("situational.sqlite", "development", "Technical Skills")


def test_captured_claim_becomes_a_usable_fact_end_to_end(drafted_application) -> None:
    """The full product path a new fact has to travel.

    An unsupported manual edit becomes a `pending` claim that blocks approval;
    the claim's own wording is captured as a `pending` fact, confirmed, promoted
    to canonical, offered to the Profile section, and only then may a claim link
    to it and validate. The draft is rebuilt after promotion because a new
    canonical fact changes the canonical surface the draft was built from.
    """
    setup = drafted_application("Lifecycle Co")
    engine, app_id = setup
    claim = _working_claim(engine, app_id, "sales.cycle.account_management")
    text = "Introduced a weekly pipeline review with the Sales team."

    _, report = engine.edit_claim(app_id, claim.claim_id, ["sales.cycle.account_management"], text=text)
    assert not report.passed
    assert any(issue.code == "pending-claim" for issue in report.issues)

    captured = engine.capture_claim_fact(
        app_id,
        claim.claim_id,
        source="sales.md",
        fact_id="sales.leadership.pipeline_review",
        meaning="Introduced a weekly pipeline review with the Sales team.",
        tags=["sales", "leadership", "pipeline"],
    )
    assert captured["fact"]["status"] == "pending"
    assert captured["fact"]["renderings"]["en"] == text
    assert captured["fact"]["resume_style"] == claim.style

    engine.promote_fact("sales.leadership.pipeline_review", "confirmed", explicitly_confirmed=True)
    engine.promote_fact("sales.leadership.pipeline_review", "canonical", explicitly_confirmed=True)

    # Canonical is necessary but not sufficient: until a Profile section offers
    # the fact, no draft may carry it and no claim may link to it.
    _, _, rebuilt_report = engine.draft(app_id)
    assert rebuilt_report.passed, rebuilt_report.model_dump()
    rebuilt = _working_claim(engine, app_id, "sales.cycle.account_management")
    _, blocked = engine.edit_claim(
        app_id, rebuilt.claim_id, ["sales.leadership.pipeline_review"], text=text
    )
    assert any(issue.code == "fact-outside-profile-section" for issue in blocked.issues)

    engine.attach_fact(
        "sales.leadership.pipeline_review", "account-manager", "Work Experience", pin=True
    )
    _, _, attached_report = engine.draft(app_id)

    assert attached_report.passed, attached_report.model_dump()
    selected = _working_claim(engine, app_id, "sales.leadership.pipeline_review")
    assert selected.claim_type == "canonical"
    assert selected.text == text
    events = engine.fact_history("sales.leadership.pipeline_review")
    assert [event["event_type"] for event in events] == [
        "fact_created",
        "fact_promoted",
        "fact_promoted",
        "fact_attached_to_profile",
    ]
    assert events[0]["application_id"] == app_id
    assert events[0]["claim_id"] == claim.claim_id


def test_attached_canonical_fact_can_be_selected_into_a_new_draft(engine: Engine) -> None:
    engine.add_fact(
        "sales.md",
        {
            "fact_id": "sales.leadership.pipeline_review",
            "meaning": "Introduced a weekly pipeline review with the Sales team.",
            "renderings": {"en": "Introduced a weekly pipeline review with the Sales team."},
            "tags": ["sales", "leadership", "pipeline"],
            "provenance": "confirmed by the user in this request",
            "resume_style": "bullet",
        },
        canonical=True,
    )
    engine.attach_fact(
        "sales.leadership.pipeline_review",
        "account-manager",
        "Work Experience",
        pin=True,
    )

    app_id, _ = engine.ingest("Selection Co", "Account Manager", ACCOUNT_MANAGER_JOB)
    engine.analyze(app_id)
    _, _, report = engine.draft(app_id)

    assert report.passed, report.model_dump()
    manifest = json.loads(
        (engine.root / "artifacts/working" / app_id / "resume.claims.json").read_text(encoding="utf-8")
    )
    assert "sales.leadership.pipeline_review" in manifest["selected_fact_ids"]
