from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.application.commands import AnalyzeCommand, DraftCommand
from cv_engine.application.errors import KnowledgeRejected
from cv_engine.runtime.composition import Services
from cv_engine.infrastructure.persistence import connect
from cv_engine.domain.facts import FactStore
from cv_engine.infrastructure.knowledge import load_fact_store, FactStoreError
from cv_engine.domain.models import FactStatus
from helpers import working_claim as _working_claim


NEW_FACT = {
    "fact_id": "situational.sqlite",
    "meaning": "Used SQLite for local application state in a personal project.",
    "renderings": {"en": "Used SQLite for local application state in a personal project."},
    "tags": ["development", "situational", "databases"],
    "provenance": "candidate wording from the user; not yet verified",
    "resume_style": "bullet",
}


def _reload(services: Services) -> FactStore:
    """Read the fact store back from disk, as a later process would."""
    return load_fact_store(services.workspace.knowledge_root / "base")


def test_new_fact_is_persisted_as_pending_and_cannot_reach_a_cv(services: Services) -> None:
    result = services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))

    assert result.fact.status is FactStatus.PENDING
    stored = _reload(services).get("situational.sqlite")
    assert stored.status is FactStatus.PENDING
    assert stored.source_file == "base/situational_skills.md"
    with pytest.raises(FactStoreError, match="not canonical"):
        _reload(services).get("situational.sqlite", canonical_only=True)


def test_pending_fact_does_not_invalidate_drafts_built_from_canonical_facts(
    services: Services,
) -> None:
    """Staging a fact for one application must not break another's draft.

    `facts.version` identifies the canonical surface a CV may be built from, so
    a `pending` fact changes `lifecycle_version` only.
    """
    before = _reload(services)
    services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))
    after = _reload(services)

    assert after.version == before.version
    assert after.lifecycle_version != before.lifecycle_version

    services.knowledge_lifecycle.promote_fact(
        "situational.sqlite", "confirmed", explicitly_confirmed=True
    )
    assert _reload(services).version == before.version

    services.knowledge_lifecycle.promote_fact(
        "situational.sqlite", "canonical", explicitly_confirmed=True
    )
    assert _reload(services).version != before.version


def test_promotion_requires_explicit_confirmation_and_a_legal_transition(
    services: Services,
) -> None:
    services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))

    with pytest.raises(KnowledgeRejected, match="explicit confirmation"):
        services.knowledge_lifecycle.promote_fact(
            "situational.sqlite", "confirmed", explicitly_confirmed=False
        )
    with pytest.raises(KnowledgeRejected, match="invalid fact transition"):
        services.knowledge_lifecycle.promote_fact(
            "situational.sqlite", "canonical", explicitly_confirmed=True
        )
    assert _reload(services).get("situational.sqlite").status is FactStatus.PENDING


def test_lifecycle_survives_process_boundaries_through_the_cli(cli_runner, v1_repo: Path) -> None:
    added = cli_runner(
        "fact",
        "add",
        "--source",
        "situational_skills.md",
        "--fact-id",
        "situational.sqlite",
        "--meaning",
        NEW_FACT["meaning"],
        "--en",
        NEW_FACT["renderings"]["en"],
        "--tag",
        "development",
        "--tag",
        "situational",
        "--style",
        "bullet",
        "--provenance",
        NEW_FACT["provenance"],
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
    assert (
        load_fact_store(v1_repo / "base").get("situational.sqlite").status is FactStatus.CANONICAL
    )

    history = json.loads(cli_runner("fact", "history", "situational.sqlite").stdout)
    assert [(event["from_status"], event["to_status"]) for event in history] == [
        (None, "pending"),
        ("pending", "confirmed"),
        ("confirmed", "canonical"),
    ]


def test_duplicate_fact_ids_are_refused(services: Services) -> None:
    services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))

    with pytest.raises(KnowledgeRejected, match="fact already exists"):
        services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))
    with pytest.raises(KnowledgeRejected, match="fact already exists"):
        services.knowledge_lifecycle.add_fact(
            "common.md", {**NEW_FACT, "meaning": "different meaning"}
        )


def test_lifecycle_events_are_immutable(services: Services) -> None:
    services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))

    with connect(services.repository.path) as connection:
        with pytest.raises(Exception, match="immutable record"):
            connection.execute("UPDATE fact_events SET to_status='canonical'")
        with pytest.raises(Exception, match="immutable record"):
            connection.execute("DELETE FROM fact_events")


def test_captured_claim_becomes_a_usable_fact_end_to_end(drafted_application) -> None:
    """The full product path a new fact has to travel.

    An unsupported manual edit becomes a `pending` claim that blocks approval;
    the claim's own wording is captured as a `pending` fact, confirmed, promoted
    to canonical, offered to the Profile section, and only then may a claim link
    to it and validate. The draft is rebuilt after promotion because a new
    canonical fact changes the canonical surface the draft was built from.
    """
    setup = drafted_application("Lifecycle Co")
    services, app_id = setup
    claim = _working_claim(services, app_id, "sales.cycle.account_management")
    text = "Introduced a weekly pipeline review with the Sales team."

    edited = services.drafts.edit_claim(
        app_id, claim.claim_id, ["sales.cycle.account_management"], text=text
    )
    assert not edited.validation.passed
    assert any(issue.code == "pending-claim" for issue in edited.validation.issues)

    captured = services.knowledge_lifecycle.capture_claim_fact(
        app_id,
        claim.claim_id,
        source="sales.md",
        fact_id="sales.leadership.pipeline_review",
        meaning="Introduced a weekly pipeline review with the Sales team.",
        tags=["sales", "leadership", "pipeline"],
    )
    assert captured.fact.status is FactStatus.PENDING
    assert captured.fact.renderings["en"] == text
    assert captured.fact.resume_style == claim.style

    services.knowledge_lifecycle.promote_fact(
        "sales.leadership.pipeline_review", "confirmed", explicitly_confirmed=True
    )
    services.knowledge_lifecycle.promote_fact(
        "sales.leadership.pipeline_review", "canonical", explicitly_confirmed=True
    )

    # Canonical is necessary but not sufficient: until a Profile section offers
    # the fact, no draft may carry it and no claim may link to it.
    rebuilt_draft = services.drafts.draft(
        DraftCommand(
            application_id=app_id,
            job_analysis_id=setup.analysis_id,
            selection_plan_id=setup.selection_plan_id,
        )
    )
    assert rebuilt_draft.validation.passed, rebuilt_draft.validation.model_dump()
    rebuilt = _working_claim(services, app_id, "sales.cycle.account_management")
    blocked = services.drafts.edit_claim(
        app_id, rebuilt.claim_id, ["sales.leadership.pipeline_review"], text=text
    )
    assert any(issue.code == "fact-outside-profile-section" for issue in blocked.validation.issues)

    services.knowledge_lifecycle.attach_fact(
        "sales.leadership.pipeline_review", "account-manager", "Work Experience", pin=True
    )
    refreshed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=app_id,
            job_snapshot_id=setup.snapshot_id,
        )
    )
    attached_draft = services.drafts.draft(
        DraftCommand(
            application_id=app_id,
            job_analysis_id=refreshed.analysis_id,
            selection_plan_id=refreshed.selection_plan_id,
        )
    )

    assert attached_draft.validation.passed, attached_draft.validation.model_dump()
    selected = _working_claim(services, app_id, "sales.leadership.pipeline_review")
    assert selected.claim_type == "canonical"
    assert selected.text == text
    events = services.knowledge_lifecycle.fact_history("sales.leadership.pipeline_review").events
    assert [event.event_type for event in events] == [
        "fact_created",
        "fact_promoted",
        "fact_promoted",
        "fact_attached_to_profile",
    ]
    assert events[0].application_id == app_id
    assert events[0].claim_id == claim.claim_id
