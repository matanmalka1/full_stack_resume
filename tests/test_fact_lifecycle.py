from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from helpers import working_claim as _working_claim

from cv_engine.application.commands import AnalyzeCommand, DraftCommand
from cv_engine.application.errors import KnowledgeRejected, PreconditionFailed
from cv_engine.application.knowledge_mutations import PrepareKnowledgeMutation
from cv_engine.domain.facts import FactStore
from cv_engine.domain.models import FactStatus
from cv_engine.infrastructure.knowledge import FactStoreError, load_fact_store
from cv_engine.infrastructure.persistence import connect
from cv_engine.runtime.composition import Services, build_services

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


def test_contextual_pending_fact_gets_a_generated_uuid(services: Services) -> None:
    payload = {key: value for key, value in NEW_FACT.items() if key != "fact_id"}
    result = services.knowledge_lifecycle.create_pending_fact(
        "situational_skills.md", payload
    )
    assert uuid.UUID(result.fact.fact_id).version == 4
    assert result.fact.status is FactStatus.PENDING
    with pytest.raises(KnowledgeRejected, match="not user-editable"):
        services.knowledge_lifecycle.create_pending_fact(
            "situational_skills.md", dict(NEW_FACT)
        )


def test_create_fact_from_claim_preserves_exact_claim_text(drafted_application) -> None:
    setup = drafted_application("Claim Knowledge Co")
    services, application_id = setup
    claim = _working_claim(services, application_id, "sales.cycle.account_management")
    exact_text = "Introduced a weekly pipeline review with the Sales team."
    services.drafts.edit_claim(
        application_id, claim.claim_id, ["sales.cycle.account_management"], text=exact_text
    )

    created = services.knowledge_lifecycle.create_fact_from_claim(
        application_id,
        claim.claim_id,
        source="sales.md",
        meaning="Introduced a weekly pipeline review with the Sales team.",
        tags=["sales", "leadership", "pipeline"],
    )

    assert uuid.UUID(created.fact.fact_id).version == 4
    assert created.fact.renderings["en"] == exact_text
    assert created.fact.status is FactStatus.PENDING


def test_knowledge_file_mutation_is_validated_staged_activated_and_restored(
    services: Services,
) -> None:
    source = services.workspace.knowledge_root / "base" / "situational_skills.md"
    before = source.read_bytes()

    staged, fact = services.knowledge.stage_create_fact(
        "staged-create",
        "situational_skills.md",
        dict(NEW_FACT),
    )
    assert fact.status is FactStatus.PENDING
    assert source.read_bytes() == before
    assert staged.source_reference == "base/situational_skills.md"
    assert staged.staged_reference == "tmp/knowledge/staged-create/new"

    services.knowledge.activate_staged(staged)
    assert _reload(services).get("situational.sqlite").status is FactStatus.PENDING
    services.knowledge.restore_staged(staged)
    assert source.read_bytes() == before
    services.knowledge.discard_staged(staged)
    assert not (services.workspace.temp_root / "knowledge" / "staged-create").exists()


def test_knowledge_file_activation_refuses_source_or_staged_hash_changes(
    services: Services,
) -> None:
    source = services.workspace.knowledge_root / "base" / "situational_skills.md"
    staged, _fact = services.knowledge.stage_create_fact(
        "source-change",
        "situational_skills.md",
        dict(NEW_FACT),
    )
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        services.knowledge.activate_staged(staged)
    source.write_text(original, encoding="utf-8")
    services.knowledge.discard_staged(staged)


@pytest.mark.parametrize("window", ["staged-missing", "staged-corrupt", "old-mismatch", "backup-missing"])
def test_prepared_knowledge_mutation_recovers_or_quarantines_from_hashes(
    services: Services, monkeypatch: pytest.MonkeyPatch, window: str
) -> None:
    def interrupt(_mutation):
        raise RuntimeError("simulated crash before activation")

    monkeypatch.setattr(services.knowledge_lifecycle, "_complete_prepared", interrupt)
    with pytest.raises(RuntimeError, match="simulated crash"):
        services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))
    mutation = services.repository.prepared_knowledge_mutations()[0]
    source = services.workspace.root / mutation.source_reference
    staged = services.workspace.root / mutation.staged_reference
    backup = staged.with_name("old")
    if window == "staged-missing":
        staged.unlink()
    elif window == "staged-corrupt":
        staged.write_text("corrupt", encoding="utf-8")
    elif window == "old-mismatch":
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    else:
        backup.unlink()

    recovered = build_services(services.workspace)
    assert recovered.repository.prepared_knowledge_mutations() == []
    quarantined = recovered.repository.quarantined_knowledge_mutations()
    assert [item.id for item in quarantined] == [mutation.id]
    assert recovered.knowledge_lifecycle.fact_history().events == []
    reconciliation = recovered.knowledge_lifecycle.reconcile_facts()
    assert not reconciliation.passed
    assert reconciliation.journal_quarantined == 1


def test_startup_finishes_crashes_before_and_after_file_activation(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_complete = services.knowledge_lifecycle._complete_prepared

    def interrupt_before(_mutation):
        raise RuntimeError("before replace")

    monkeypatch.setattr(services.knowledge_lifecycle, "_complete_prepared", interrupt_before)
    with pytest.raises(RuntimeError, match="before replace"):
        services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))
    mutation = services.repository.prepared_knowledge_mutations()[0]
    with pytest.raises(KnowledgeRejected, match="uncommitted prepared mutation"):
        services.knowledge_lifecycle.list_facts()
    assert services.knowledge_lifecycle.fact_history().events == []

    monkeypatch.setattr(services.knowledge_lifecycle, "_complete_prepared", original_complete)
    recovered = build_services(services.workspace)
    assert recovered.repository.knowledge_mutation(mutation.id).state.value == "COMMITTED"
    assert _reload(recovered).get("situational.sqlite").status is FactStatus.PENDING
    assert len(recovered.knowledge_lifecycle.fact_history("situational.sqlite").events) == 1

    second_payload = {**NEW_FACT, "fact_id": "situational.sqlite.second"}

    def interrupt_after(mutation):
        staged = recovered.knowledge.staged_from_mutation(mutation)
        recovered.knowledge.activate_staged(staged)
        raise RuntimeError("after replace")

    monkeypatch.setattr(recovered.knowledge_lifecycle, "_complete_prepared", interrupt_after)
    with pytest.raises(RuntimeError, match="after replace"):
        recovered.knowledge_lifecycle.add_fact("situational_skills.md", second_payload)
    recovered_again = build_services(services.workspace)
    assert (
        _reload(recovered_again).get("situational.sqlite.second").status is FactStatus.PENDING
    )
    assert len(recovered_again.knowledge_lifecycle.fact_history().events) == 2


def test_startup_marks_committed_db_mutation_without_duplicate_event(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_commit = services.repository.commit_knowledge_mutation
    calls = 0

    def fail_once(mutation_id: str, *, committed_at: str | None = None):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("after SQLite commit")
        return original_commit(mutation_id, committed_at=committed_at)

    monkeypatch.setattr(services.repository, "commit_knowledge_mutation", fail_once)
    with pytest.raises(RuntimeError, match="after SQLite commit"):
        services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))
    assert len(services.repository.fact_events("situational.sqlite")) == 1
    assert len(services.repository.prepared_knowledge_mutations()) == 1

    recovered = build_services(services.workspace)
    assert recovered.repository.prepared_knowledge_mutations() == []
    assert len(recovered.repository.fact_events("situational.sqlite")) == 1


def test_audit_failure_restores_source_and_quarantines(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = services.workspace.knowledge_root / "base" / "situational_skills.md"
    before = source.read_bytes()

    def refuse_event(self, **_values):
        raise ValueError("simulated audit insertion failure")

    monkeypatch.setattr(type(services.repository), "record_fact_event", refuse_event)
    with pytest.raises(KnowledgeRejected, match="audit insertion failure"):
        services.knowledge_lifecycle.add_fact("situational_skills.md", dict(NEW_FACT))
    assert source.read_bytes() == before
    assert len(services.repository.quarantined_knowledge_mutations()) == 1
    with pytest.raises(KnowledgeRejected, match="mutations are quarantined"):
        services.knowledge_lifecycle.add_fact(
            "situational_skills.md", {**NEW_FACT, "fact_id": "another.fact"}
        )


def test_quarantine_blocks_approval_but_keeps_history_readable(drafted_application) -> None:
    setup = drafted_application("Quarantine Co")
    services, application_id = setup
    request = PrepareKnowledgeMutation(
        mutation_id="quarantined-mutation",
        mutation_type="promote_fact",
        source_reference="base/sales.md",
        staged_reference="tmp/knowledge/quarantined-mutation/new",
        old_sha256="a" * 64,
        new_sha256="b" * 64,
        db_mutation_type="fact_event",
        db_mutation_id="quarantined-event",
        db_mutation={"actions": []},
        recovery_strategy="finish_or_restore",
    )
    services.repository.prepare_knowledge_mutation(request)
    services.repository.quarantine_knowledge_mutation(request.mutation_id, "unrecoverable")

    assert services.knowledge_lifecycle.fact_history().events == []
    with pytest.raises(PreconditionFailed, match="approval blocked by quarantined Knowledge"):
        services.drafts.approve(application_id)


def test_confirm_and_use_is_one_journaled_fact_profile_and_plan_command(
    drafted_application,
) -> None:
    setup = drafted_application("Contextual Knowledge Co")
    services, application_id = setup
    created = services.knowledge_lifecycle.add_fact(
        "sales.md",
        {
            **NEW_FACT,
            "fact_id": "sales.contextual.pipeline_review",
            "tags": ["sales", "leadership", "pipeline"],
        },
        application_id=application_id,
    )

    result = services.knowledge_lifecycle.confirm_and_use_fact(
        created.fact.fact_id,
        application_id=application_id,
        job_analysis_id=setup.analysis_id,
        profile="account-manager",
        section="Work Experience",
    )

    assert result.fact.status is FactStatus.CANONICAL
    assert created.fact.fact_id in result.selection_plan.plan.selected_fact_ids
    assert result.selection_plan.id != setup.selection_plan_id
    assert result.selection_plan.profile_version == result.profile_store_version
    events = services.knowledge_lifecycle.fact_history(created.fact.fact_id).events
    assert [(event.from_status, event.to_status) for event in events] == [
        (None, "pending"),
        ("pending", "confirmed"),
        ("confirmed", "canonical"),
        ("canonical", "canonical"),
    ]
    assert len(result.event_ids) == 3
    assert services.repository.prepared_knowledge_mutations() == []
    assert services.repository.quarantined_knowledge_mutations() == []


def test_selection_plan_failure_restores_both_knowledge_files_and_quarantines(
    drafted_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = drafted_application("Contextual Rollback Co")
    services, application_id = setup
    created = services.knowledge_lifecycle.add_fact(
        "sales.md",
        {
            **NEW_FACT,
            "fact_id": "sales.contextual.rollback",
            "tags": ["sales", "leadership", "pipeline"],
        },
        application_id=application_id,
    )
    fact_source = services.workspace.knowledge_root / "base" / "sales.md"
    profile_source = services.workspace.knowledge_root / "profiles" / "sales" / "account-manager.yaml"
    before_fact = fact_source.read_bytes()
    before_profile = profile_source.read_bytes()

    def refuse_plan(self, *_args, **_kwargs):
        raise ValueError("simulated SelectionPlan constraint failure")

    monkeypatch.setattr(type(services.repository), "create_selection_plan", refuse_plan)
    with pytest.raises(KnowledgeRejected, match="SelectionPlan constraint failure"):
        services.knowledge_lifecycle.confirm_and_use_fact(
            created.fact.fact_id,
            application_id=application_id,
            job_analysis_id=setup.analysis_id,
            profile="account-manager",
            section="Work Experience",
        )

    assert fact_source.read_bytes() == before_fact
    assert profile_source.read_bytes() == before_profile
    assert _reload(services).get(created.fact.fact_id).status is FactStatus.PENDING
    assert len(services.repository.quarantined_knowledge_mutations()) == 1

    staged, _fact = services.knowledge.stage_create_fact(
        "stage-change",
        "situational_skills.md",
        dict(NEW_FACT),
    )
    staged_path = services.workspace.root / staged.staged_reference
    staged_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="staged Knowledge file hash mismatch"):
        services.knowledge.activate_staged(staged)
    services.knowledge.discard_staged(staged)


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


def test_lifecycle_survives_process_boundaries_through_the_cli(
    cli_subprocess, workspace_root: Path
) -> None:
    added = cli_subprocess(
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

    unconfirmed = cli_subprocess("fact", "confirm", "situational.sqlite")
    assert unconfirmed.returncode == 2
    assert "requires explicit --confirm" in unconfirmed.stderr

    assert cli_subprocess("fact", "confirm", "situational.sqlite", "--confirm").returncode == 0
    assert cli_subprocess("fact", "promote", "situational.sqlite", "--confirm").returncode == 0

    listed = cli_subprocess("fact", "list", "--status", "canonical")
    assert listed.returncode == 0
    ids = [fact["fact_id"] for fact in json.loads(listed.stdout)]
    assert "situational.sqlite" in ids
    assert (
        load_fact_store(workspace_root / "base").get("situational.sqlite").status is FactStatus.CANONICAL
    )

    history = json.loads(cli_subprocess("fact", "history", "situational.sqlite").stdout)
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
