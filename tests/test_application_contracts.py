"""The application layer's declared contracts: results, errors, and ports.

M1 requires command/query DTOs, stable error types, focused repository ports,
and a UnitOfWork. These tests hold those in place, because a contract that is
only described in a document drifts the first time a service is edited.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from helpers import ACCOUNT_MANAGER_JOB, working_claim
from pydantic import BaseModel

from cv_engine.application import errors
from cv_engine.application.commands import (
    AnalysisResult,
    AnalyzeCommand,
    ApplicationMutationResult,
    ApprovalResult,
    DraftCommand,
    DraftResult,
    EditResult,
    FactDetailResult,
    FactListResult,
    FactReconciliationResult,
    IngestCommand,
    IngestedApplication,
    KnowledgeVersionsResult,
    NextActionCommand,
    RecruitmentStatusCommand,
    RenderResult,
)
from cv_engine.application.ports import (
    ApplicationRepository,
    ApplicationStore,
    ArtifactRegistry,
    FactAudit,
    JobStore,
    SnapshotPayload,
    UnitOfWork,
)
from cv_engine.application.queries import (
    ApplicationListView,
    ArtifactVersionView,
    DecisionRecordView,
    JobSnapshotView,
)
from cv_engine.application.services.rendering import RenderingService
from cv_engine.cli import _latest_job_analysis_id, _latest_job_snapshot_id
from cv_engine.infrastructure.persistence import Repository
from cv_engine.util import sha256_file, sha256_text

# --- results are typed, not positional --------------------------------------


def test_commands_answer_with_named_results(services) -> None:
    ingested = services.applications.ingest(
        IngestCommand(
            company="Named Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
        )
    )
    assert isinstance(ingested, IngestedApplication)
    assert isinstance(ingested, BaseModel)

    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    assert isinstance(analysed, AnalysisResult)
    assert analysed.analysis.track.value

    drafted = services.drafts.draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )
    )
    assert isinstance(drafted, DraftResult)
    assert drafted.validation.passed, drafted.validation.model_dump()

    approved = services.drafts.approve(ingested.application_id)
    assert isinstance(approved, ApprovalResult)
    assert approved.version == 1


def test_ingest_commits_exact_snapshot_payload_before_registration(
    services, monkeypatch: pytest.MonkeyPatch
) -> None:
    received = "Line one\r\nLine two\n"
    original_create = services.repository.create_application

    def assert_payload_exists_first(**values):
        payload = services.workspace.root / values["payload_path"]
        assert payload.read_bytes() == received.encode("utf-8")
        assert sha256_text(received) == values["source_hash"]
        return original_create(**values)

    monkeypatch.setattr(services.repository, "create_application", assert_payload_exists_first)
    ingested = services.applications.ingest(
        IngestCommand(
            company="Payload Order",
            target_role="Developer",
            job_text=received,
        )
    )
    snapshot = services.repository.get_snapshot(ingested.job_snapshot_id)
    assert (
        sha256_file(services.workspace.root / snapshot["payload_path"]) == snapshot["source_hash"]
    )


def test_application_dtos_do_not_expose_filesystem_locations(services) -> None:
    for model in (
        AnalysisResult,
        DraftResult,
        EditResult,
        ApprovalResult,
        RenderResult,
        JobSnapshotView,
        ArtifactVersionView,
    ):
        assert "path" not in model.model_fields
        assert all("Path" not in str(field.annotation) for field in model.model_fields.values())
    assert "path" not in SnapshotPayload.__dataclass_fields__
    assert all(
        "Path" not in str(field.type) for field in SnapshotPayload.__dataclass_fields__.values()
    )

    ingested = services.applications.ingest(
        IngestCommand(
            company="Projection Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
        )
    )
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    services.drafts.draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )
    )
    services.drafts.approve(ingested.application_id)

    projection = services.queries.artifact_versions(ingested.application_id)
    serialized = projection.model_dump(mode="json")
    assert serialized["items"]
    assert all("path" not in item and "metadata_json" not in item for item in serialized["items"])


def test_knowledge_query_and_reconciliation_services_return_typed_results(services) -> None:
    knowledge = services.knowledge_lifecycle

    versions = knowledge.knowledge_versions()
    assert isinstance(versions, KnowledgeVersionsResult)
    assert all(versions.model_dump().values())

    facts = knowledge.list_facts("canonical")
    assert isinstance(facts, FactListResult)
    assert facts.items
    assert all(item.fact.status.value == "canonical" for item in facts.items)

    detail = knowledge.show_fact(facts.items[0].fact.fact_id)
    assert isinstance(detail, FactDetailResult)
    assert detail.fact == facts.items[0].fact

    reconciliation = knowledge.reconcile_facts()
    assert isinstance(reconciliation, FactReconciliationResult)
    assert reconciliation.passed, reconciliation.problems


def test_draft_link_and_markdown_sync_services_preserve_validation(drafted_application) -> None:
    setup = drafted_application("Editing Boundary Co")
    claim = working_claim(setup.services, setup.application_id, "common.language.hebrew")

    linked = setup.services.drafts.link_claim(
        setup.application_id,
        claim.claim_id,
        claim.text,
        claim.fact_ids,
    )
    assert linked.validation.passed, linked.validation.model_dump()

    synchronized = setup.services.drafts.sync_working_claims(setup.application_id)
    assert synchronized.validation.passed, synchronized.validation.model_dump()


def test_query_and_tracking_services_expose_the_application_boundary(approved_application) -> None:
    setup = approved_application("Query Boundary Co")
    services = setup.services

    applications = services.queries.list_applications()
    assert isinstance(applications, ApplicationListView)
    assert setup.application_id in {item.id for item in applications.items}

    decision = services.queries.latest_decision(setup.application_id)
    assert isinstance(decision, DecisionRecordView)
    assert decision.id == setup.approved.decision_record_id

    transitioned = services.tracking.transition_status(
        RecruitmentStatusCommand(
            application_id=setup.application_id,
            target_status="withdrawn",
            reason="boundary contract test",
        )
    )
    assert isinstance(transitioned, ApplicationMutationResult)
    assert transitioned.current_status == "withdrawn"

    next_action = services.tracking.set_next_action(
        NextActionCommand(
            application_id=setup.application_id,
            next_action="Archive evidence",
            next_action_date="2026-08-20",
        )
    )
    assert isinstance(next_action, ApplicationMutationResult)
    assert next_action.current_status == "withdrawn"
    assert next_action.next_action == "Archive evidence"
    assert next_action.next_action_date == "2026-08-20"


# --- refusals are typed -----------------------------------------------------


def test_refusals_share_one_taxonomy_and_report_missing_dependencies(services) -> None:
    """One base class, so an outer layer can catch the layer rather than a list."""
    for name in (
        "UnknownRecord",
        "StateConflict",
        "ValidationBlocked",
        "LineageBroken",
        "KnowledgeRejected",
        "DependencyUnavailable",
        "InfrastructureFailure",
        "PreconditionFailed",
    ):
        assert issubclass(getattr(errors, name), errors.ApplicationError)
    assert errors.WorkflowError is errors.ApplicationError
    rendering = RenderingService(
        repository=services.repository,
        knowledge=services.knowledge,
        artifacts=services.artifacts,
        renderer=None,
    )
    with pytest.raises(errors.DependencyUnavailable, match="renderer"):
        _ = rendering.renderer


def test_expected_boundary_refusals_do_not_leak_adapter_or_domain_errors(services) -> None:
    with pytest.raises(errors.PreconditionFailed, match="required"):
        services.applications.ingest(
            IngestCommand(
                company="",
                target_role="Account Manager",
                job_text=ACCOUNT_MANAGER_JOB,
            )
        )

    with pytest.raises(errors.UnknownRecord, match="job snapshot"):
        services.analysis.analyze(
            AnalyzeCommand(
                application_id="missing-application",
                job_snapshot_id="missing-snapshot",
            )
        )

    with pytest.raises(errors.UnknownRecord, match="job analysis"):
        services.drafts.draft(
            DraftCommand(
                application_id="missing-application",
                job_analysis_id="missing-analysis",
                selection_plan_id="missing-selection-plan",
            )
        )


def test_a_blocked_validation_carries_its_report(drafted_application) -> None:
    setup = drafted_application("Blocked Co")
    services, application_id = setup
    markdown = setup.markdown
    claim = working_claim(services, application_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(
            claim.text, "Delivered 30% improvement in direct SaaS Sales.", 1
        ),
        encoding="utf-8",
    )
    services.drafts.sync_working_claims(application_id)

    with pytest.raises(errors.ValidationBlocked) as raised:
        services.drafts.approve(application_id)

    assert raised.value.report is not None
    assert not raised.value.report.passed


# --- ports are focused and expose no adapter internals -----------------------


def test_repository_satisfies_focused_ports_without_leaking_adapter_internals(
    tmp_path: Path,
) -> None:
    repository = Repository(tmp_path / "applications.sqlite3")
    for port in (ApplicationStore, JobStore, ArtifactRegistry, FactAudit):
        for name in port.__protocol_attrs__:
            assert callable(getattr(repository, name)), f"{port.__name__}.{name}"
    leaked = {"path", "transaction", "connection"} & set(ApplicationRepository.__protocol_attrs__)
    assert not leaked, leaked
    private = {name for name in ApplicationRepository.__protocol_attrs__ if name.startswith("_")}
    assert not private, private


# --- the unit of work is a real boundary -------------------------------------


def test_unit_of_work_commits_success_and_rolls_back_failure(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "applications.sqlite3")
    with repository.unit_of_work() as unit:
        assert isinstance(unit, UnitOfWork)
        unit.connection.execute(
            "INSERT INTO applications (id, company, target_role, normalized_role, language, "
            "current_status, created_at, updated_at) "
            "VALUES ('a', 'Co', 'Role', 'Role', 'en', 'saved', '2026-01-01', '2026-01-01')"
        )
        unit.commit()

    assert repository.get_application("a")["company"] == "Co"
    with pytest.raises(RuntimeError):
        with repository.unit_of_work() as unit:
            unit.connection.execute(
                "INSERT INTO applications (id, company, target_role, normalized_role, language, "
                "current_status, created_at, updated_at) "
                "VALUES ('b', 'Co', 'Role', 'Role', 'en', 'saved', '2026-01-01', '2026-01-01')"
            )
            raise RuntimeError("command refused after writing")

    with pytest.raises(errors.UnknownRecord):
        repository.get_application("b")

    with repository.unit_of_work() as unit:
        unit.connection.execute(
            "INSERT INTO applications (id, company, target_role, normalized_role, language, "
            "current_status, created_at, updated_at) "
            "VALUES ('c', 'Co', 'Role', 'Role', 'en', 'saved', '2026-01-01', '2026-01-01')"
        )
    with pytest.raises(errors.UnknownRecord):
        repository.get_application("c")


# --- commands take explicit sources; `latest` lives outside them --------------


def test_commands_require_owned_explicit_sources_and_cli_resolves_latest(services) -> None:
    mine = services.applications.ingest(
        IngestCommand(
            company="Mine Co", target_role="Account Manager", job_text=ACCOUNT_MANAGER_JOB
        )
    )
    theirs = services.applications.ingest(
        IngestCommand(
            company="Theirs Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    )

    with pytest.raises(errors.LineageBroken, match="does not belong"):
        services.analysis.analyze(
            AnalyzeCommand(
                application_id=mine.application_id,
                job_snapshot_id=theirs.job_snapshot_id,
            )
        )

    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=theirs.application_id,
            job_snapshot_id=theirs.job_snapshot_id,
        )
    )
    with pytest.raises(errors.LineageBroken, match="does not belong"):
        services.drafts.draft(
            DraftCommand(
                application_id=mine.application_id,
                job_analysis_id=analysed.analysis_id,
                selection_plan_id=analysed.selection_plan_id,
            )
        )
    ingested = services.applications.ingest(
        IngestCommand(
            company="Legacy Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
        )
    )

    assert (
        _latest_job_snapshot_id(services.repository, ingested.application_id)
        == ingested.job_snapshot_id
    )

    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    assert (
        _latest_job_analysis_id(services.repository, ingested.application_id)
        == analysed.analysis_id
    )
    from cv_engine.application.services.drafts import DraftService

    # Operation execution split generation into prepare/activate; source
    # resolution remains in the preparation half of the same application service.
    source = inspect.getsource(DraftService.prepare)
    assert "latest_analysis" not in source
    assert source.count("latest_snapshot(") == 1
