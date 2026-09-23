"""The application -> snapshot -> analysis -> draft -> approval -> decision chain.

Every test here asserts two things about a rejected operation: that it is
rejected, and that it left nothing behind. A guard that raises after writing an
artifact, a decision, an analysis, or an application field is not a guard.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from helpers import (
    ACCOUNT_MANAGER_JOB,
    AMBIGUOUS_HEBREW_JOB,
    approve_active_draft,
    seed_analysis_for_command,
    validate_active_draft,
    working_draft_paths,
)
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import ProgrammingError

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import (
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    DraftCommand,
    IngestCommand,
)
from cv_engine.application.errors import (
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    WorkflowError,
)
from cv_engine.domain.contracts.records import DecisionRecord
from cv_engine.domain.draft_markdown import parse_draft
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.decision_store import SqlAlchemyDecisionRepository
from cv_engine.infrastructure.persistence.draft_lifecycle import (
    SqlAlchemyDraftLifecycleRepository,
)
from cv_engine.infrastructure.persistence.job_snapshots import SqlAlchemyJobSnapshotStore
from cv_engine.infrastructure.persistence.tables import (
    approved_revisions,
    decision_records,
    metadata,
)
from cv_engine.infrastructure.persistence.validation_store import SqlAlchemyValidationRepository
from cv_engine.runtime.composition import Services
from cv_engine.runtime.paths import AppPaths
from cv_engine.util import normalized_text, sha256_file, sha256_text, utc_now


def _rows(database_engine, table) -> list[dict]:
    with database_engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(table)).mappings()]


def _register(transaction_manager, *args, **kwargs):
    with transaction_manager.write() as tx:
        return SqlAlchemyArtifactCatalog(transaction_manager).register_artifact_version(
            tx, *args, **kwargs
        )


def _persisted(database_engine) -> dict[str, int]:
    """Row counts for every product table, discovered rather than listed.

    A rejected command must leave nothing behind anywhere, so this counts the whole
    database instead of a remembered set of tables filtered by application_id. That
    covers indirect records with no application_id column of their own — artifact
    versions, selection plans, working drafts — and, more importantly, covers the
    next table automatically: a list would have gone on passing while a new table
    quietly gained a row.
    """
    with database_engine.connect() as connection:
        return {
            table.name: connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in metadata.sorted_tables
        }


def _analyze(services: Services, transaction_manager, application_id: str, **overrides):
    with transaction_manager.read() as tx:
        snapshot_id = SqlAlchemyApplicationProjectionReader(transaction_manager).latest_snapshot(
            tx, application_id
        )["id"]
    analysis_values = {
        key: overrides[key]
        for key in ("requirements", "user_override", "summary", "keywords")
        if key in overrides
    }
    return seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=application_id,
            job_snapshot_id=snapshot_id,
            track_override=overrides.get("track"),
            profile_override=overrides.get("profile"),
            emphasis_override=overrides.get("emphasis"),
            language_override=overrides.get("language"),
        ),
        **analysis_values,
    )


def _draft(services: Services, transaction_manager, application_id: str, analysis_id: str):
    with transaction_manager.read() as tx:
        plan = SqlAlchemyApplicationProjectionReader(transaction_manager).latest_selection_plan(
            tx, application_id
        )
    assert plan is not None
    return services.drafts.draft(
        DraftCommand(
            application_id=application_id,
            job_analysis_id=analysis_id,
            selection_plan_id=plan.id,
        )
    )


# --- 1. a plan may only be drafted from while its context still holds ------


def test_moved_snapshot_or_moved_knowledge_requires_a_new_analysis_before_drafting(
    project_root: Path, analyzed_application, transaction_manager, database_engine
) -> None:
    services, app_id = analyzed_application("Snapshot Race")
    with transaction_manager.read() as tx:
        analysis_record = SqlAlchemyApplicationProjectionReader(transaction_manager).analyses(
            tx, app_id
        )[-1]
    analysis_id = analysis_record["id"]
    stale_analysis_id = analysis_id
    new_text = ACCOUNT_MANAGER_JOB + " The role also covers quarterly portfolio reviews."
    new_snapshot_id = str(uuid.uuid4())
    payload = services.payloads.commit_snapshot(app_id, new_snapshot_id, new_text)
    with transaction_manager.write() as tx:
        SqlAlchemyJobSnapshotStore(transaction_manager).insert_next_snapshot(
            tx,
            application_id=app_id,
            payload_path=payload.reference,
            source_hash=payload.sha256,
            normalized_hash=sha256_text(normalized_text(new_text)),
            snapshot_id=new_snapshot_id,
            source_url=None,
            source_metadata={},
            captured_at=utc_now(),
        )
    before = _persisted(database_engine)

    with pytest.raises(WorkflowError, match="snapshot"):
        _draft(services, transaction_manager, app_id, stale_analysis_id)

    assert not (project_root / "artifacts/working" / app_id).exists()
    assert _persisted(database_engine) == before

    # Analyzing the new snapshot unblocks drafting, and the draft binds both ends
    # of the chain exactly rather than inheriting a "latest" of either kind.
    analysed = _analyze(services, transaction_manager, app_id)
    assert analysed.analysis_id != stale_analysis_id
    drafted = _draft(services, transaction_manager, app_id, analysed.analysis_id)
    manifest = working_draft_paths(services, app_id).manifest
    assert drafted.validation.passed, drafted.validation.model_dump()
    draft = parse_draft(manifest.read_text(encoding="utf-8"))
    assert draft.job_analysis_id == analysed.analysis_id
    assert draft.job_snapshot_id == new_snapshot_id

    # The plan also freezes the knowledge it selected under, and a frozen
    # version only guards anything if editing that knowledge moves it. The
    # emphasis policy version stored here is therefore the store's content hash
    # rather than the "1.0.0" label the policy files declare and the manifest
    # carries, which no policy edit touches.
    versions = services.knowledge_queries.knowledge_versions()
    with transaction_manager.read() as tx:
        plan = SqlAlchemyApplicationProjectionReader(transaction_manager).latest_selection_plan(
            tx, app_id
        )
    assert plan.profile_version == versions.profiles
    assert plan.selection_policy_version == versions.emphasis_policies
    assert plan.selection_policy_version != plan.plan.policy_version

    # Editing a policy without touching its declared label is exactly the change
    # the column exists to detect: the plan's section assignment was decided
    # under weights that no longer hold, so drafting from it refuses.
    policy_file = project_root / "config" / "emphasis.json"
    original_policy = policy_file.read_text(encoding="utf-8")
    policy = json.loads(original_policy)
    policy["emphases"]["development-balanced"]["tag_weights"]["testing"] += 1
    policy_file.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    before_policy_edit = _persisted(database_engine)

    with pytest.raises(StateConflict, match="selection policy"):
        _draft(services, transaction_manager, app_id, analysed.analysis_id)

    assert _persisted(database_engine) == before_policy_edit
    # Analyzing again freezes the edited policy, and drafting proceeds.
    reanalysed = _analyze(services, transaction_manager, app_id)
    with transaction_manager.read() as tx:
        replanned = SqlAlchemyApplicationProjectionReader(
            transaction_manager
        ).latest_selection_plan(tx, app_id)
    assert replanned.selection_policy_version != plan.selection_policy_version
    assert replanned.plan.policy_version == plan.plan.policy_version
    assert _draft(services, transaction_manager, app_id, reanalysed.analysis_id).validation.passed
    policy_file.write_text(original_policy, encoding="utf-8")


# --- 2. a newer material analysis invalidates an older working draft -------


def test_newer_material_analysis_invalidates_the_working_draft(
    project_root: Path, drafted_application, transaction_manager, database_engine
) -> None:
    setup = drafted_application("Emphasis Drift")
    services, app_id = setup.services, setup.application_id
    drafted_analysis_id = parse_draft(setup.manifest.read_text(encoding="utf-8")).job_analysis_id
    newer = _analyze(services, transaction_manager, app_id, emphasis="balanced-sales")
    assert newer.analysis.emphasis.value == "balanced-sales"
    assert newer.analysis_id != drafted_analysis_id
    before = _persisted(database_engine)

    with pytest.raises(WorkflowError, match="analysis"):
        approve_active_draft(services, app_id)

    assert not (project_root / "artifacts" / app_id).exists()
    assert _persisted(database_engine) == before

    # Re-drafting under the newer analysis is the way forward, and the decision
    # record then binds that analysis.
    drafted = _draft(services, transaction_manager, app_id, newer.analysis_id)
    manifest = working_draft_paths(services, app_id).manifest
    assert drafted.validation.passed, drafted.validation.model_dump()
    assert parse_draft(manifest.read_text(encoding="utf-8")).job_analysis_id == newer.analysis_id
    approve_active_draft(services, app_id)
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationProjectionReader(transaction_manager).latest_decision(tx, app_id)[
                "job_analysis_id"
            ]
            == newer.analysis_id
        )


def test_approval_binds_the_exact_frozen_lineage_and_payloads_before_registration(
    drafted_application,
    monkeypatch: pytest.MonkeyPatch,
    project_root: Path,
    transaction_manager,
    database_engine,
) -> None:
    """A re-run that changes nothing material leaves the draft valid -- and the
    approval still records the analysis the draft was actually built from."""
    setup = drafted_application("Rerun Analysis")
    services, app_id = setup.services, setup.application_id
    bound_analysis_id = parse_draft(setup.manifest.read_text(encoding="utf-8")).job_analysis_id
    with transaction_manager.read() as tx:
        bound_analysis = SqlAlchemyApplicationProjectionReader(transaction_manager).analysis(
            tx, bound_analysis_id
        )["analysis"]
    # A re-run that reproduces the same classification changes nothing
    # material (README, "Default workflow"). Mirroring every material field
    # `drafted_application`'s real, accepted-incomplete analysis actually
    # carries - rather than guessing at a matching shape - is what makes this
    # a same-classification re-run instead of a materially different one.
    rerun = _analyze(
        services,
        transaction_manager,
        app_id,
        requirements=bound_analysis.requirements,
        user_override=bound_analysis.user_override,
        summary=bound_analysis.summary,
        keywords=bound_analysis.keywords,
    )
    assert rerun.analysis_id != bound_analysis_id
    with transaction_manager.read() as tx:
        working = SqlAlchemyApplicationProjectionReader(transaction_manager).active_working_draft(
            tx, app_id
        )
    with transaction_manager.read() as tx:
        plan = SqlAlchemyApplicationProjectionReader(transaction_manager).selection_plan(
            tx, working.selection_plan_id
        )

    # A historical artifact row must not participate in the ApprovedRevision
    # sequence. It remains unbound, while revision 1's markdown is artifact
    # version 2 for the existing logical artifact.
    _register(
        transaction_manager,
        app_id,
        "resume_markdown",
        "resume",
        f"artifacts/historical/{app_id}/resume.md",
        "0" * 64,
        "approved",
        job_snapshot_id=working.source.job_snapshot_id,
    )

    original_create = SqlAlchemyDraftLifecycleRepository.create_approved_revision
    observed: dict[str, bool] = {}

    def require_payloads_first(repository, *args, **kwargs):
        for reference, expected_hash in ((args[5], args[6]), (args[7], args[8])):
            path = project_root / reference
            assert path.is_file()
            assert sha256_file(path) == expected_hash
        observed["payloads_precede_row"] = True
        return original_create(repository, *args, **kwargs)

    monkeypatch.setattr(
        SqlAlchemyDraftLifecycleRepository, "create_approved_revision", require_payloads_first
    )

    approved = approve_active_draft(services, app_id)

    with transaction_manager.read() as tx:
        decision = SqlAlchemyApplicationProjectionReader(transaction_manager).latest_decision(
            tx, app_id
        )
    assert decision["job_analysis_id"] == bound_analysis_id
    assert json.loads(decision["structured_json"])["job_analysis_id"] == bound_analysis_id
    assert observed == {"payloads_precede_row": True}
    assert approved.version == 1
    with transaction_manager.read() as tx:
        revision = SqlAlchemyApplicationProjectionReader(transaction_manager).approved_revision(
            tx, approved.revision_id
        )
    with transaction_manager.read() as tx:
        lineage = SqlAlchemyValidationRepository(transaction_manager).validation_lineage(
            tx, revision.validation_run_id
        )
    assert revision.application_id == app_id
    assert revision.job_snapshot_id == working.source.job_snapshot_id
    assert revision.job_analysis_id == working.job_analysis_id == bound_analysis_id
    assert revision.selection_plan_id == working.selection_plan_id
    assert revision.working_draft_id == working.id
    assert revision.draft_edit_version == working.edit_version
    assert revision.draft_content_hash == working.content_hash
    assert revision.candidate_context_version == plan.candidate_context_version
    assert revision.candidate_context_hash == plan.candidate_context_hash
    assert revision.profile_version == plan.profile_version
    assert revision.selection_policy_version == plan.selection_policy_version
    assert revision.track_emphasis_dependencies == plan.track_emphasis_dependencies
    assert revision.knowledge_context_hash == lineage.knowledge_context_hash
    assert revision.validator_versions == lineage.validator_versions
    assert revision.decision_provenance == {
        "actor_type": "user",
        "client": "web",
        "command": "approve_draft",
    }
    revision_root = Path("artifacts/revisions") / app_id / revision.id
    json_reference = Path(revision.resume_json_reference)
    markdown_reference = Path(revision.resume_markdown_reference)
    assert json_reference.parent.parent == revision_root
    assert markdown_reference.parent == json_reference.parent
    assert json_reference.name == "resume.json"
    assert markdown_reference.name == "resume.md"
    assert uuid.UUID(json_reference.parent.name).version == 4
    assert sha256_file(project_root / revision.resume_json_reference) == revision.resume_json_hash
    assert (
        sha256_file(project_root / revision.resume_markdown_reference)
        == revision.resume_markdown_hash
    )
    assert (
        parse_draft((project_root / revision.resume_json_reference).read_text(encoding="utf-8"))
        == working.source
    )

    with transaction_manager.read() as tx:
        versions = SqlAlchemyApplicationProjectionReader(transaction_manager).artifact_versions(
            tx, app_id
        )
    current = [row for row in versions if row["revision_id"] == revision.id]
    assert {row["artifact_type"] for row in current} == {
        "resume_markdown",
        "claim_manifest",
    }
    assert (
        next(row for row in current if row["artifact_type"] == "resume_markdown")["version_number"]
        == 2
    )
    assert (
        next(row for row in current if row["artifact_type"] == "claim_manifest")["path"]
        == revision.resume_json_reference
    )
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationProjectionReader(transaction_manager)
            .working_draft(tx, working.id)
            .active
            is False
        )
    with pytest.raises(UnknownRecord, match="active working draft"):
        with transaction_manager.read() as tx:
            SqlAlchemyDraftLifecycleRepository(transaction_manager).active_working_draft(tx, app_id)

    for statement in (
        update(approved_revisions)
        .where(approved_revisions.c.id == revision.id)
        .values(draft_content_hash=approved_revisions.c.draft_content_hash),
        delete(approved_revisions).where(approved_revisions.c.id == revision.id),
    ):
        with pytest.raises(ProgrammingError, match="immutable record"):
            with database_engine.begin() as connection:
                connection.execute(statement)


def test_latest_decision_uses_revision_order_when_approvals_share_a_timestamp(
    ai_api_paused, drafted_application, monkeypatch: pytest.MonkeyPatch, transaction_manager
) -> None:
    """The record explains one document, so it names that document's language.

    Asserted across two approvals in two languages on one Application. With a
    single language in play, a record that had copied the current analysis would
    pass every assertion here, so the second revision is what makes the first
    record's value mean anything: it is read back while both the latest analysis
    and the newest revision say the other language.
    """
    fixed_approval_time = "2026-08-23T12:34:56Z"
    monkeypatch.setattr(
        "cv_engine.application.services.drafts.approval.utc_now", lambda: fixed_approval_time
    )

    setup = drafted_application("Decision Language")
    services, app_id = setup.services, setup.application_id

    def language_of(revision_id: str) -> str:
        # By revision, never `latest`: `utc_now` is second-resolution, so two
        # approvals inside one second tie on `created_at` and `latest_decision`
        # answers with whichever row the ordering happens to reach first.
        with transaction_manager.read() as tx:
            record = SqlAlchemyDecisionRepository(transaction_manager).decision_for_revision(
                tx, revision_id
            )
        return json.loads(record["structured_json"])["language"]

    english = parse_draft(setup.manifest.read_text(encoding="utf-8"))
    assert english.language == "en"
    first = approve_active_draft(services, app_id)

    assert language_of(first.revision_id) == english.language
    first_export = services.draft_history.export_decision_markdown(
        app_id, first.revision_id
    ).content
    assert "- Language: en" in first_export

    hebrew_analysis = _analyze(services, transaction_manager, app_id, language="he")
    _draft(services, transaction_manager, app_id, hebrew_analysis.analysis_id)
    hebrew = parse_draft(setup.manifest.read_text(encoding="utf-8"))
    assert hebrew.language == "he"
    second = approve_active_draft(services, app_id)

    assert language_of(second.revision_id) == hebrew.language == "he"
    second_export = services.draft_history.export_decision_markdown(
        app_id, second.revision_id
    ).content
    assert "- Language: he" in second_export

    with transaction_manager.read() as tx:
        first_record = SqlAlchemyDecisionRepository(transaction_manager).decision_for_revision(
            tx, first.revision_id
        )
    with transaction_manager.read() as tx:
        second_record = SqlAlchemyDecisionRepository(transaction_manager).decision_for_revision(
            tx, second.revision_id
        )
    assert first_record["created_at"] == second_record["created_at"] == fixed_approval_time
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationProjectionReader(transaction_manager).latest_decision(tx, app_id)[
                "id"
            ]
            == second_record["id"]
        )

    api = ai_api_paused.client
    latest = api.get(f"{API_PREFIX}/applications/{app_id}/decision")
    assert latest.status_code == 200
    assert latest.json()["id"] == second_record["id"]
    assert latest.json()["structured"]["language"] == "he"

    # Re-read the first record with the latest analysis and the newest revision
    # both in Hebrew: the export renders what was stored, not what is current.
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationProjectionReader(transaction_manager)
            .analyses(tx, app_id)[-1]["analysis"]
            .language
            == "he"
        )
    assert language_of(first.revision_id) == "en"
    reread = services.draft_history.export_decision_markdown(app_id, first.revision_id).content
    assert reread == first_export
    assert "- Language: en" in reread
    assert "- Language: he" not in reread
    assert "- Language: \n" not in reread


# --- 3. records may not cross application ownership boundaries -------------


def test_approval_builds_typed_decision_and_artifacts_cannot_cross_applications(
    drafted_application,
    monkeypatch: pytest.MonkeyPatch,
    transaction_manager,
    database_engine,
) -> None:
    owner = drafted_application("Owner Co")
    stranger = drafted_application("Stranger Co", role="Key Account Manager")
    services = owner.services
    inserted: list[DecisionRecord] = []
    original_insert = SqlAlchemyDecisionRepository.insert_decision

    def capture_insert(repository, tx, record: DecisionRecord) -> None:
        assert isinstance(record, DecisionRecord)
        inserted.append(record)
        original_insert(repository, tx, record)

    monkeypatch.setattr(SqlAlchemyDecisionRepository, "insert_decision", capture_insert)
    approved = approve_active_draft(services, owner.application_id)
    with transaction_manager.read() as tx:
        owner_markdown = SqlAlchemyArtifactCatalog(transaction_manager).latest_artifact_version(
            tx, owner.application_id, "resume_markdown", "approved"
        )
    with transaction_manager.read() as tx:
        stranger_snapshot_id = SqlAlchemyApplicationProjectionReader(
            transaction_manager
        ).latest_snapshot(tx, stranger.application_id)["id"]
    with transaction_manager.read() as tx:
        owner_snapshot_id = SqlAlchemyApplicationProjectionReader(
            transaction_manager
        ).latest_snapshot(tx, owner.application_id)["id"]
    with transaction_manager.read() as tx:
        owner_analysis_id = SqlAlchemyApplicationProjectionReader(transaction_manager).analyses(
            tx, owner.application_id
        )[-1]["id"]
    assert len(inserted) == 1
    decision = inserted[0]
    assert decision.application_id == owner.application_id
    assert decision.artifact_version_id == owner_markdown["id"]
    assert decision.job_snapshot_id == owner_snapshot_id
    assert decision.job_analysis_id == owner_analysis_id
    assert decision.id == approved.decision_record_id
    before = _persisted(database_engine)

    with pytest.raises(LineageBroken, match="application"):
        _register(
            transaction_manager,
            owner.application_id,
            "resume_markdown",
            "cross-owner",
            "artifacts/cross-owner.md",
            "0" * 64,
            "approved",
            job_snapshot_id=stranger_snapshot_id,
        )

    assert _persisted(database_engine) == before
    assert [row["application_id"] for row in _rows(database_engine, decision_records)] == [
        owner.application_id
    ]


# --- 4. an invalid Track/Profile/Emphasis pair mutates nothing -------------


def test_invalid_classifications_are_rejected_before_any_persistence(
    services: Services, transaction_manager, database_engine
) -> None:
    cases = [
        ({"track": "development", "profile": "account-manager"}, "Track"),
        ({"profile": "account-manager", "emphasis": "leadership"}, "mphasis"),
    ]
    for index, (overrides, match) in enumerate(cases):
        ingested = services.applications.ingest(
            IngestCommand(
                company=f"Inconsistent Co {index}",
                target_role="Account Manager",
                job_text=ACCOUNT_MANAGER_JOB,
                acknowledged_duplicates=True,
                client="web",
            )
        )
        app_id = ingested.application_id
        with transaction_manager.read() as tx:
            before_application = SqlAlchemyApplicationProjectionReader(
                transaction_manager
            ).application(tx, app_id)
        before = _persisted(database_engine)
        with pytest.raises(WorkflowError, match=match):
            _analyze(services, transaction_manager, app_id, **overrides)
        with transaction_manager.read() as tx:
            assert (
                SqlAlchemyApplicationProjectionReader(transaction_manager).application(tx, app_id)
                == before_application
            )
        assert _persisted(database_engine) == before
        with transaction_manager.read() as tx:
            assert (
                SqlAlchemyApplicationProjectionReader(transaction_manager).analyses(tx, app_id)
                == []
            )


# --- the chain is validated as one unit ------------------------------------


def test_projection_manifest_changes_do_not_mutate_the_working_draft_record(
    project_root: Path, drafted_application, transaction_manager
) -> None:
    setup = drafted_application("Tampered Chain")
    services, app_id = setup.services, setup.application_id
    manifest = project_root / "artifacts/working" / app_id / "resume.claims.json"
    original = manifest.read_text(encoding="utf-8")
    with transaction_manager.read() as tx:
        authoritative = SqlAlchemyApplicationProjectionReader(
            transaction_manager
        ).active_working_draft(tx, app_id)
    cases = [
        ("track", "development"),
        ("emphasis", "balanced-sales"),
        ("language", "he"),
        ("job_snapshot_id", "not-a-snapshot"),
        ("fact_store_version", "0" * 64),
    ]
    for field, value in cases:
        payload = json.loads(original)
        payload[field] = value
        manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        assert validate_active_draft(services, app_id).passed
        assert not (project_root / "artifacts" / app_id).exists()
        with transaction_manager.read() as tx:
            assert (
                SqlAlchemyApplicationProjectionReader(transaction_manager).active_working_draft(
                    tx, app_id
                )
                == authoritative
            )
    manifest.write_text(original, encoding="utf-8")


# --- ready integrity independently rechecks the chain ----------------------


def test_ready_qualification_is_not_invalidated_by_material_reanalysis(
    app_paths: AppPaths, ready_application, transaction_manager
) -> None:
    services, app_id = ready_application("Chain Recheck")
    with transaction_manager.read() as tx:
        revision_id = (
            SqlAlchemyDraftLifecycleRepository(transaction_manager)
            .latest_approved_revision(tx, app_id)
            .id
        )
    assert services.rendering.ready_qualification(app_id).ready_qualified

    _analyze(services, transaction_manager, app_id, emphasis="balanced-sales")

    qualification = services.rendering.ready_qualification(app_id, revision_id)
    assert qualification.ready_qualified, qualification.validation.model_dump()


def test_ready_integrity_holds_through_an_immaterial_reanalysis(
    app_paths: AppPaths, ready_application, transaction_manager
) -> None:
    """A re-run that changes nothing material is not a reason to fail integrity."""
    services, app_id = ready_application("Immaterial Rerun")
    _analyze(services, transaction_manager, app_id)
    qualification = services.rendering.ready_qualification(app_id)
    assert qualification.ready_qualified, qualification.validation.model_dump()
    with transaction_manager.read() as tx:
        revision_id = (
            SqlAlchemyDraftLifecycleRepository(transaction_manager)
            .latest_approved_revision(tx, app_id)
            .id
        )
    with transaction_manager.read() as tx:
        assert {
            row["artifact_type"]
            for row in SqlAlchemyApplicationProjectionReader(transaction_manager).artifact_versions(
                tx, app_id
            )
            if row["revision_id"] == revision_id
        } == {
            "resume_markdown",
            "claim_manifest",
            "resume_html",
            "resume_pdf",
        }


def test_the_requirement_vocabulary_stales_an_analysis_and_nothing_after_it(
    services: Services, project_root: Path
) -> None:
    """A draft consumes the analysis, never the vocabulary that produced it.

    One hash covered every dependency, so editing `config/requirements.json`
    declared the inputs of a draft, its validation, its approval and a render
    changed - none of which read that file. A submitted draft then failed
    activation, and a recorded validation stopped describing its own draft,
    because a file they had never opened moved.
    """
    knowledge = services.knowledge.load()
    before_analysis = knowledge.context_hash()
    before_document = knowledge.document_context_hash()
    assert before_analysis != before_document, "the two scopes must not be the same hash"
    assert set(knowledge.versions()) - set(knowledge.document_versions()) == {
        "requirement_concepts"
    }

    concepts = project_root / "config" / "requirements.json"
    payload = json.loads(concepts.read_text(encoding="utf-8"))
    payload["policy_version"] = "changed-for-this-test"
    concepts.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    after = services.knowledge.load()
    assert after.context_hash() != before_analysis, "the analysis must see the vocabulary move"
    assert after.document_context_hash() == before_document


def test_no_stage_after_analysis_reads_the_requirement_vocabulary(project_root: Path) -> None:
    """The exclusion is justified by consumption, so consumption is what is checked.

    Derived from the package rather than from a list of stages: a module that
    starts reading the vocabulary and is not registered here fails, because the
    document scope would then be excluding a dependency that stage really has.
    """
    allowed = {
        # Where the store is defined, loaded, and reported.
        Path("cv_engine/domain/knowledge.py"),
        Path("cv_engine/infrastructure/knowledge.py"),
        Path("cv_engine/api/routers/health.py"),
        Path("cv_engine/api/schemas/health.py"),
        Path("cv_engine/application/commands/knowledge.py"),
        # Preparation and interpretation correction consume it.
        Path("cv_engine/application/services/analysis/preparation.py"),
        Path("cv_engine/application/services/analysis/correction.py"),
    }
    root = Path(__file__).resolve().parents[1]
    readers = {
        path.relative_to(root)
        for path in (root / "cv_engine").rglob("*.py")
        if "requirement_concepts" in path.read_text(encoding="utf-8")
    }
    assert readers <= allowed, (
        "these read the requirement vocabulary but are excluded from the document "
        f"knowledge scope: {sorted(str(path) for path in readers - allowed)}"
    )


def test_a_fact_overlay_still_may_not_ride_a_classification_decision(
    services: Services, database_engine
) -> None:
    """The refusal narrowed to what it was actually about.

    A fact overlay is decided against candidate accounting the new analysis has
    not produced yet, so it stays a second command.
    """
    ingested = services.applications.ingest(
        IngestCommand(
            company="Fact Overlay Co",
            target_role="Account Manager",
            job_text=AMBIGUOUS_HEBREW_JOB,
            client="web",
        )
    )
    analysed = seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        ),
    )
    before = _persisted(database_engine)
    with pytest.raises(PreconditionFailed, match="fact overlay"):
        services.analysis.apply_analysis_decisions(
            ApplyAnalysisDecisionsCommand(
                application_id=ingested.application_id,
                job_analysis_id=analysed.analysis_id,
                expected_analysis_id=analysed.analysis_id,
                expected_selection_plan_id=analysed.selection_plan_id,
                profile_override="account-manager",
                excluded_fact_ids=["sales.company.activity"],
            )
        )
    assert _persisted(database_engine) == before
