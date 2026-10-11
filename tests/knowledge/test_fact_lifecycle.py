from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from helpers import (
    approve_active_draft,
    edit_document_claim,
    persisted_counts,
    seed_analysis_for_command,
    seed_draft,
    services_transactions,
    stored_document,
    validate_active_draft,
)
from helpers import working_claim as _working_claim
from pydantic import ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import ProgrammingError

from cv_engine.api.schemas.facts import CaptureClaimFactRequest
from cv_engine.application.commands import AnalyzeCommand, BuildFromAnalysisCommand
from cv_engine.application.errors import (
    KnowledgeRejected,
    StateConflict,
    UnknownRecord,
)
from cv_engine.application.knowledge_mutations import PrepareKnowledgeMutation
from cv_engine.domain.contracts.knowledge import FactStatus
from cv_engine.domain.facts import FactStore
from cv_engine.infrastructure.knowledge import FactStoreError
from cv_engine.infrastructure.persistence.knowledge_lifecycle import (
    SqlAlchemyKnowledgeLifecycleRepository,
)
from cv_engine.infrastructure.persistence.tables import candidate_contexts, fact_events
from cv_engine.infrastructure.persistence.user_knowledge import SqlAlchemyUserKnowledgeRepository
from cv_engine.runtime.composition import Services, build_services
from cv_engine.runtime.paths import AppPaths

NEW_FACT = {
    "fact_id": "situational.postgres",
    "meaning": "Used PostgreSQL for local application state in a personal project.",
    "renderings": {"en": "Used PostgreSQL for local application state in a personal project."},
    "tags": ["development", "situational", "databases"],
    "provenance": "candidate wording from the user; not yet verified",
    "resume_style": "bullet",
}


def _knowledge_persistence(services: Services):
    transactions = services_transactions(services)
    return transactions, SqlAlchemyKnowledgeLifecycleRepository(transactions)


def _reload(services: Services) -> FactStore:
    """Read the fact store back from the database, as a later process would."""
    return build_services(services.paths).knowledge.facts()


def _fact_store_version(database_engine) -> int:
    with database_engine.connect() as connection:
        return connection.execute(select(candidate_contexts.c.fact_store_version)).scalar_one()


def test_new_fact_is_pending_cannot_reach_a_cv_and_contextual_identity_is_generated(
    services: Services,
) -> None:
    result = services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))

    assert result.fact.status is FactStatus.PENDING
    stored = _reload(services).get("situational.postgres")
    assert stored.status is FactStatus.PENDING
    assert stored.source_file == "base/situational_skills.json"
    with pytest.raises(FactStoreError, match="not canonical"):
        _reload(services).get("situational.postgres", canonical_only=True)

    payload = {key: value for key, value in NEW_FACT.items() if key != "fact_id"}
    contextual = services.knowledge_lifecycle.create_pending_fact(
        "situational_skills.json", payload
    )
    assert uuid.UUID(contextual.fact.fact_id).version == 4
    assert contextual.fact.status is FactStatus.PENDING
    with pytest.raises(KnowledgeRejected, match="not user-editable"):
        services.knowledge_lifecycle.create_pending_fact("situational_skills.json", dict(NEW_FACT))


def test_attachment_target_projection_exposes_sections_without_profile_documents(
    services: Services,
) -> None:
    targets = services.knowledge_queries.fact_attachment_targets()
    development = next(item for item in targets.profiles if item.profile == "development")
    assert development.label
    assert development.sections
    assert all(not section.attached and not section.pinned for section in development.sections)

    knowledge = services.knowledge_lifecycle.load_knowledge()
    source_profile = knowledge.profiles.get("development")
    source_section = next(section for section in source_profile.sections if section.fact_ids)
    existing_id = source_section.fact_ids[0]
    existing = services.knowledge_queries.fact_attachment_targets(existing_id)
    projected_profile = next(item for item in existing.profiles if item.profile == "development")
    projected_section = next(
        item for item in projected_profile.sections if item.section == source_section.name_en
    )
    assert projected_section.attached
    assert projected_section.pinned is (existing_id in source_section.pinned_fact_ids)

    with pytest.raises(UnknownRecord, match="unknown fact_id"):
        services.knowledge_queries.fact_attachment_targets("does-not-exist")


def test_create_fact_from_claim_preserves_exact_claim_text(drafted_application) -> None:
    setup = drafted_application("Claim Knowledge Co")
    services, application_id = setup
    claim = _working_claim(services, application_id, "sales.cycle.account_management")
    exact_text = "Introduced a weekly pipeline review with the Sales team."
    edit_document_claim(
        services,
        application_id,
        claim.claim_id,
        ["sales.cycle.account_management"],
        text=exact_text,
    )

    created = services.knowledge_lifecycle.create_fact_from_claim(
        application_id,
        claim.claim_id,
        source="sales.json",
        meaning="Introduced a weekly pipeline review with the Sales team.",
        tags=["sales", "leadership", "pipeline"],
    )

    assert uuid.UUID(created.fact.fact_id).version == 4
    assert created.fact.renderings["en"] == exact_text
    assert created.fact.status is FactStatus.PENDING


def _refuse_events(services: Services, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_event(self, _tx, **_values):
        raise ValueError("simulated audit insertion failure")

    _transactions, store = _knowledge_persistence(services)
    monkeypatch.setattr(type(store), "record_fact_event", refuse_event)


def test_audit_failure_writes_no_part_of_the_mutation(
    services: Services, monkeypatch: pytest.MonkeyPatch, database_engine
) -> None:
    """The fact, its event and the fact-store version are one transaction (§18.2)."""
    before = persisted_counts(database_engine)
    version = _fact_store_version(database_engine)
    _refuse_events(services, monkeypatch)

    with pytest.raises(ValueError, match="audit insertion failure"):
        services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))

    assert persisted_counts(database_engine) == before
    assert _fact_store_version(database_engine) == version
    assert "situational.postgres" not in _reload(services).facts


def test_a_quarantined_journal_entry_is_history_and_blocks_nothing(drafted_application) -> None:
    """The retired journal's rows are history (architecture §7.2): one left quarantined
    is reported by reconciliation, and blocks neither approval nor a fact mutation."""
    setup = drafted_application("Quarantine Co")
    services, application_id = setup
    request = PrepareKnowledgeMutation(
        mutation_id=str(uuid.uuid4()),
        mutation_type="fact_confirmed",
        source_reference="base/sales.json",
        staged_reference="tmp/knowledge/quarantined-mutation/new",
        old_sha256="a" * 64,
        new_sha256="b" * 64,
        db_mutation_type="fact_event",
        db_mutation_id="quarantined-event",
        db_mutation={"actions": []},
        recovery_strategy="finish_or_restore",
    )
    transactions, store = _knowledge_persistence(services)
    with transactions.write() as tx:
        store.prepare_mutation(tx, request)
    with transactions.write() as tx:
        store.quarantine_mutation(tx, request.mutation_id, "unrecoverable")

    assert services.knowledge_queries.fact_history().events == []
    assert approve_active_draft(services, application_id).passed
    services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))
    reconciliation = services.knowledge_queries.reconcile_facts()
    assert reconciliation.journal_quarantined == 1
    assert not reconciliation.passed


def test_confirm_and_use_is_one_journaled_fact_and_profile_command(
    drafted_application,
) -> None:
    """§17: confirm and attach in one mutation; the document is not written."""
    setup = drafted_application("Contextual Knowledge Co")
    services, application_id = setup
    created = services.knowledge_lifecycle.add_fact(
        "sales.json",
        {
            **NEW_FACT,
            "fact_id": "sales.contextual.pipeline_review",
            "tags": ["sales", "leadership", "pipeline"],
        },
        application_id=application_id,
    )

    before = stored_document(services, application_id)
    result = services.knowledge_lifecycle.confirm_and_use_fact(
        created.fact.fact_id,
        application_id=application_id,
        job_analysis_id=setup.analysis_id,
        profile="account-manager",
        section="Work Experience",
    )

    assert result.fact.status is FactStatus.CANONICAL
    assert stored_document(services, application_id) == before
    assert before.id == result.document_id
    assert before.document_hash == result.document_hash == setup.document_hash
    profile = services.knowledge.load().profiles.get("account-manager")
    work = next(spec for spec in profile.sections if spec.name_en == "Work Experience")
    assert created.fact.fact_id in work.fact_ids
    events = services.knowledge_queries.fact_history(created.fact.fact_id).events
    assert [(event.from_status, event.to_status) for event in events] == [
        (None, "pending"),
        ("pending", "canonical"),
        ("canonical", "canonical"),
    ]
    assert len(result.event_ids) == 2
    transactions, store = _knowledge_persistence(services)
    with transactions.read() as tx:
        assert store.prepared_mutations(tx) == []
        assert store.quarantined_mutations(tx) == []


def test_a_mutation_from_a_stale_read_is_refused_not_merged(
    services: Services, monkeypatch: pytest.MonkeyPatch, database_engine
) -> None:
    """The fact-store version is the optimistic check between two mutations (§18.2).

    A second command that read Knowledge before the first one committed would write
    over it; it is refused instead, and writes nothing.
    """
    transactions = services_transactions(services)
    with transactions.read() as tx:
        stale = services.knowledge.state(tx)
    services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))
    before = persisted_counts(database_engine)
    monkeypatch.setattr(services.knowledge, "state", lambda _tx: stale)

    with pytest.raises(StateConflict, match="changed while it was being written"):
        services.knowledge_lifecycle.add_fact(
            "situational_skills.json", {**NEW_FACT, "fact_id": "situational.concurrent"}
        )

    assert persisted_counts(database_engine) == before


def test_confirm_and_use_audit_failure_leaves_the_fact_and_the_binding_as_they_were(
    drafted_application, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = drafted_application("Contextual Rollback Co")
    services, application_id = setup
    created = services.knowledge_lifecycle.add_fact(
        "sales.json",
        {
            **NEW_FACT,
            "fact_id": "sales.contextual.rollback",
            "tags": ["sales", "leadership", "pipeline"],
        },
        application_id=application_id,
    )
    profile_before = services.knowledge.load().profiles.get("account-manager")
    _refuse_events(services, monkeypatch)

    with pytest.raises(ValueError, match="audit insertion failure"):
        services.knowledge_lifecycle.confirm_and_use_fact(
            created.fact.fact_id,
            application_id=application_id,
            job_analysis_id=setup.analysis_id,
            profile="account-manager",
            section="Work Experience",
        )

    assert _reload(services).get(created.fact.fact_id).status is FactStatus.PENDING
    assert services.knowledge.load().profiles.get("account-manager") == profile_before


def test_an_unrelated_fact_change_leaves_a_document_approvable(drafted_application) -> None:
    """Only the facts a document depends on are its concern (state-and-use-cases §6).

    A fact created and confirmed for nothing this document cites moves the canonical
    surface (`facts.version`) but not the document's basis, and the document still
    passes its check and approves: there is no store-wide version check to fail.
    """
    setup = drafted_application("Unrelated Fact Co")
    services, application_id = setup
    before = _reload(services)
    services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))
    after = _reload(services)
    assert after.version == before.version
    assert after.lifecycle_version != before.lifecycle_version

    services.knowledge_lifecycle.confirm_fact("situational.postgres", explicitly_confirmed=True)
    assert _reload(services).version != before.version

    approved = approve_active_draft(services, application_id)
    assert approved.passed, approved.report


def test_lifecycle_refuses_unconfirmed_illegal_duplicate_and_repeated_deletion(
    services: Services,
) -> None:
    """Confirmation needs explicit attestation and a pending fact; a fact ID is
    unique across every source; and deletion is confirmed, one-way, excluded from
    the default listing and targets, and keeps the lifecycle trail."""
    services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))

    with pytest.raises(KnowledgeRejected, match="explicit confirmation"):
        services.knowledge_lifecycle.confirm_fact(
            "situational.postgres", explicitly_confirmed=False
        )
    assert _reload(services).get("situational.postgres").status is FactStatus.PENDING

    with pytest.raises(KnowledgeRejected, match="fact already exists"):
        services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))
    with pytest.raises(KnowledgeRejected, match="fact already exists"):
        services.knowledge_lifecycle.add_fact(
            "common.json", {**NEW_FACT, "meaning": "different meaning"}
        )

    fact_id = "situational.postgres"

    with pytest.raises(KnowledgeRejected, match="explicit confirmation"):
        services.knowledge_lifecycle.delete_fact(fact_id, explicitly_confirmed=False)

    deleted = services.knowledge_lifecycle.delete_fact(fact_id, explicitly_confirmed=True)
    assert deleted.fact.status is FactStatus.DELETED
    stored = _reload(services).get(fact_id)
    assert stored.status is FactStatus.DELETED

    # One-way: deleting an already-deleted fact is refused.
    with pytest.raises(KnowledgeRejected, match="already deleted"):
        services.knowledge_lifecycle.delete_fact(fact_id, explicitly_confirmed=True)

    # Excluded from the default listing; still reachable by explicit filter and by ID.
    default_listing = services.knowledge_queries.list_facts()
    assert fact_id not in {item.fact.fact_id for item in default_listing.items}
    deleted_listing = services.knowledge_queries.list_facts("deleted")
    assert fact_id in {item.fact.fact_id for item in deleted_listing.items}
    assert services.knowledge_queries.show_fact(fact_id).fact.status is FactStatus.DELETED

    # Excluded from attachment targets, and refused by confirm/attach.
    with pytest.raises(UnknownRecord, match="deleted"):
        services.knowledge_queries.fact_attachment_targets(fact_id)
    with pytest.raises(KnowledgeRejected, match="only a pending fact can be confirmed"):
        services.knowledge_lifecycle.confirm_fact(fact_id, explicitly_confirmed=True)
    with pytest.raises(KnowledgeRejected, match="only canonical facts"):
        services.knowledge_lifecycle.attach_fact(fact_id, "account-manager", "Work Experience")

    # The lifecycle trail is preserved, not erased.
    history = services.knowledge_queries.fact_history(fact_id)
    assert [event.to_status for event in history.events] == ["pending", "deleted"]


def test_lifecycle_survives_process_boundaries_over_http(
    live_api_server, project_root: Path, database_url: str
) -> None:
    """The HTTP fact journey, each step a separate request against a separately started server.

    The in-process API tests share one composition root, so they cannot show
    that a promotion is durable rather than held in a live object graph. Here
    every call crosses a real socket into a process this test did not build,
    and the final assertion reads the fact back from the database in this one.
    """
    created = live_api_server.post(
        "/facts",
        {
            "source": "situational_skills.json",
            "meaning": NEW_FACT["meaning"],
            "renderings": NEW_FACT["renderings"],
            "tags": ["development", "situational"],
            "provenance": NEW_FACT["provenance"],
            "resume_style": "bullet",
        },
    )
    assert created.status == 201, created.body
    fact_id = created.json["fact"]["fact_id"]
    assert created.json["fact"]["status"] == "pending"
    assert created.json["fact"]["meaning"] == NEW_FACT["meaning"]
    assert created.json["event_id"]
    # Identity is generated, never supplied: the caller could not have chosen it.
    assert fact_id and fact_id != "situational.postgres"

    # Confirmation is explicit: an unconfirmed transition is refused rather
    # than assumed, and the refusal must not advance the fact.
    unconfirmed = live_api_server.post(f"/facts/{fact_id}/confirm", {"confirm": False})
    assert unconfirmed.status == 412, unconfirmed.body

    confirmed = live_api_server.post(f"/facts/{fact_id}/confirm", {"confirm": True})
    assert confirmed.status == 200, confirmed.body
    assert confirmed.json["fact"]["status"] == "canonical"
    # Confirmation is the one step: a canonical fact has nothing left to confirm.
    again = live_api_server.post(f"/facts/{fact_id}/confirm", {"confirm": True})
    assert again.status == 412, again.body

    detail = live_api_server.get(f"/facts/{fact_id}")
    assert detail.status == 200, detail.body
    assert detail.json["fact"]["fact_id"] == fact_id
    assert detail.json["events"], "a created fact has at least its creation event"

    listed = live_api_server.get("/facts", params={"status": "canonical"})
    assert listed.status == 200, listed.body
    assert fact_id in {item["fact"]["fact_id"] for item in listed.json["items"]}

    history = live_api_server.get(f"/facts/{fact_id}/history")
    assert history.status == 200, history.body
    transitions = [(event["from_status"], event["to_status"]) for event in history.json["events"]]
    assert transitions == [
        (None, "pending"),
        ("pending", "canonical"),
    ]

    # The database is the record, not the server's memory.
    reader = build_services(AppPaths.from_root(project_root), database_url=database_url)
    stored = reader.knowledge.facts().get(fact_id)
    assert stored.status is FactStatus.CANONICAL


def test_lifecycle_events_are_immutable_and_carry_their_owner(services: Services) -> None:
    result = services.knowledge_lifecycle.add_fact("situational_skills.json", dict(NEW_FACT))
    transactions, store = _knowledge_persistence(services)
    with transactions.read() as tx:
        owner = SqlAlchemyUserKnowledgeRepository(transactions).sole_user_id(tx)
        recorded = (
            transactions.connection_for(tx)
            .execute(select(fact_events.c.user_id).where(fact_events.c.id == result.event_id))
            .scalar_one()
        )
    assert recorded == owner is not None

    with pytest.raises(ProgrammingError, match="immutable record"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(update(fact_events).values(to_status="canonical"))
    with pytest.raises(ProgrammingError, match="immutable record"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(delete(fact_events))

    # The one permitted change: an owner for an event written before there was one,
    # NULL -> a user, with nothing else (migration 0005).
    fact = result.fact
    with transactions.write() as tx:
        legacy = store.record_fact_event(
            tx,
            fact_id=fact.fact_id,
            source_file=fact.source_file,
            event_type="fact_created",
            from_status=None,
            to_status=fact.status.value,
            fact=fact.model_dump(mode="json"),
            facts_version="before",
            lifecycle_version="before",
        )
    unowned = update(fact_events).where(fact_events.c.id == legacy)
    with pytest.raises(ProgrammingError, match="immutable record"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(unowned.values(user_id=owner, reason="changed"))
    with transactions.write() as tx:
        connection = transactions.connection_for(tx, access="write")
        connection.execute(unowned.values(user_id=owner))
    with pytest.raises(ProgrammingError, match="immutable record"):
        with transactions.write() as tx:
            connection = transactions.connection_for(tx, access="write")
            connection.execute(unowned.values(user_id=None))


def test_captured_claim_becomes_a_usable_fact_end_to_end(drafted_application) -> None:
    """The full product path a new fact has to travel.

    An unsupported manual edit becomes a `pending` claim that blocks approval;
    the claim's own wording is captured as a `pending` fact, confirmed as
    canonical, offered to the Profile section, and only then may a claim link
    to it and validate. The draft is rebuilt after confirmation because a new
    canonical fact changes the canonical surface the draft was built from.
    """
    # Capture over HTTP names its provenance explicitly; it is never defaulted.
    with pytest.raises(ValidationError):
        CaptureClaimFactRequest.model_validate(
            {
                "application_id": "application",
                "claim_id": "claim",
                "source": "sales.json",
                "meaning": "candidate introduced a weekly pipeline review",
                "tags": ["sales", "pipeline"],
            }
        )

    setup = drafted_application("Lifecycle Co")
    services, app_id = setup
    claim = _working_claim(services, app_id, "sales.cycle.account_management")
    text = "Introduced a weekly pipeline review with the Sales team."

    edited = edit_document_claim(
        services, app_id, claim.claim_id, ["sales.cycle.account_management"], text=text
    )
    assert claim.claim_id in edited.pending_claim_ids
    assert not validate_active_draft(services, app_id).passed

    captured = services.knowledge_lifecycle.capture_claim_fact(
        app_id,
        claim.claim_id,
        source="sales.json",
        fact_id="sales.leadership.pipeline_review",
        meaning="Introduced a weekly pipeline review with the Sales team.",
        tags=["sales", "leadership", "pipeline"],
    )
    assert captured.fact.status is FactStatus.PENDING
    assert captured.fact.renderings["en"] == text
    assert captured.fact.resume_style == claim.style

    services.knowledge_lifecycle.confirm_fact(
        "sales.leadership.pipeline_review", explicitly_confirmed=True
    )

    edit_document_claim(
        services, app_id, claim.claim_id, ["sales.leadership.pipeline_review"], text=text
    )
    checked = validate_active_draft(services, app_id)
    assert not checked.passed
    assert any(issue.code == "fact-outside-profile-section" for issue in checked.report.issues)

    services.knowledge_lifecycle.attach_fact(
        "sales.leadership.pipeline_review", "account-manager", "Work Experience", pin=True
    )
    refreshed = seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=app_id,
            job_text_hash=setup.job_text_hash,
        ),
    )
    services.draft_editing.build_from_analysis(
        BuildFromAnalysisCommand(
            application_id=app_id,
            analysis_id=refreshed.analysis_id,
            expected_document_hash=stored_document(services, app_id).document_hash,
        )
    )
    seed_draft(services, app_id)
    assert validate_active_draft(services, app_id).passed
    selected = _working_claim(services, app_id, "sales.leadership.pipeline_review")
    assert selected.claim_type == "canonical"
    assert selected.text == text
    events = services.knowledge_queries.fact_history("sales.leadership.pipeline_review").events
    assert [event.event_type for event in events] == [
        "fact_created",
        "fact_confirmed",
        "fact_attached_to_profile",
    ]
    assert events[0].application_id == app_id
    assert events[0].claim_id == claim.claim_id
