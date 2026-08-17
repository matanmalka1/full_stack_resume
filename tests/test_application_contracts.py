"""The application layer's declared contracts: results, errors, and ports.

M1 requires command/query DTOs, stable error types, focused repository ports,
and a UnitOfWork. These tests hold those in place, because a contract that is
only described in a document drifts the first time a service is edited.
"""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest
from pydantic import BaseModel

from cv_engine.application import errors
from cv_engine.application.commands import (
    AnalyzeCommand,
    AnalysisResult,
    ApprovalResult,
    DraftCommand,
    DraftResult,
    IngestCommand,
    IngestedApplication,
    RenderResult,
)
from cv_engine.application.queries import ArtifactVersionView
from cv_engine.application.ports import (
    ApplicationRepository,
    ApplicationStore,
    ArtifactRegistry,
    FactAudit,
    JobStore,
    UnitOfWork,
)
from cv_engine.application.services import RenderingService
from cv_engine.compat import resolve_job_analysis_id, resolve_job_snapshot_id
from cv_engine.infrastructure.db import Repository
from helpers import ACCOUNT_MANAGER_JOB


# --- results are typed, not positional --------------------------------------


def test_commands_answer_with_named_results(engine) -> None:
    services = engine.services

    ingested = services.applications.ingest(IngestCommand(
        company="Named Co",
        target_role="Account Manager",
        job_text=ACCOUNT_MANAGER_JOB,
    ))
    assert isinstance(ingested, IngestedApplication)
    assert isinstance(ingested, BaseModel)

    analysed = services.analysis.analyze(AnalyzeCommand(
        application_id=ingested.application_id,
        job_snapshot_id=ingested.job_snapshot_id,
    ))
    assert isinstance(analysed, AnalysisResult)
    assert analysed.analysis.track.value

    drafted = services.drafts.draft(DraftCommand(
        application_id=ingested.application_id,
        job_analysis_id=analysed.analysis_id,
    ))
    assert isinstance(drafted, DraftResult)
    assert drafted.validation.passed, drafted.validation.model_dump()

    approved = services.drafts.approve(ingested.application_id)
    assert isinstance(approved, ApprovalResult)
    assert approved.version == 1


def test_application_dtos_do_not_expose_filesystem_locations(engine) -> None:
    for model in (DraftResult, ApprovalResult, RenderResult, ArtifactVersionView):
        assert "path" not in model.model_fields
        assert all("Path" not in str(field.annotation) for field in model.model_fields.values())

    ingested = engine.services.applications.ingest(IngestCommand(
        company="Projection Co",
        target_role="Account Manager",
        job_text=ACCOUNT_MANAGER_JOB,
    ))
    analysed = engine.services.analysis.analyze(AnalyzeCommand(
        application_id=ingested.application_id,
        job_snapshot_id=ingested.job_snapshot_id,
    ))
    engine.services.drafts.draft(DraftCommand(
        application_id=ingested.application_id,
        job_analysis_id=analysed.analysis_id,
    ))
    engine.services.drafts.approve(ingested.application_id)

    projection = engine.services.queries.artifact_versions(ingested.application_id)
    serialized = projection.model_dump(mode="json")
    assert serialized["items"]
    assert all("path" not in item and "metadata_json" not in item for item in serialized["items"])


# --- refusals are typed -----------------------------------------------------


def test_refusals_share_one_taxonomy_and_report_missing_dependencies(engine) -> None:
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
        repository=engine.services.repository,
        knowledge=engine.services.knowledge,
        artifacts=engine.services.artifacts,
        renderer=None,
    )
    with pytest.raises(errors.DependencyUnavailable, match="renderer"):
        rendering.renderer


def test_expected_boundary_refusals_do_not_leak_adapter_or_domain_errors(engine) -> None:
    with pytest.raises(errors.PreconditionFailed, match="required"):
        engine.services.applications.ingest(IngestCommand(
            company="",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
        ))

    with pytest.raises(errors.UnknownRecord, match="job snapshot"):
        engine.services.analysis.analyze(AnalyzeCommand(
            application_id="missing-application",
            job_snapshot_id="missing-snapshot",
        ))

    with pytest.raises(errors.UnknownRecord, match="job analysis"):
        engine.services.drafts.draft(DraftCommand(
            application_id="missing-application",
            job_analysis_id="missing-analysis",
        ))


def test_a_blocked_validation_carries_its_report(drafted_application) -> None:
    setup = drafted_application("Blocked Co")
    engine, application_id = setup
    markdown = setup.markdown
    markdown.write_text(markdown.read_text(encoding="utf-8") + "\n- Grew revenue 30% YoY.\n", encoding="utf-8")

    with pytest.raises(errors.ValidationBlocked) as raised:
        engine.services.drafts.approve(application_id)

    assert raised.value.report is not None
    assert not raised.value.report.passed


# --- ports are focused and expose no adapter internals -----------------------


def test_repository_satisfies_focused_ports_without_leaking_adapter_internals(tmp_path: Path) -> None:
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
            "VALUES ('a', 'Co', 'Role', 'Role', 'en', 'draft', '2026-01-01', '2026-01-01')"
        )
        unit.commit()

    assert repository.get_application("a")["company"] == "Co"
    with pytest.raises(RuntimeError):
        with repository.unit_of_work() as unit:
            unit.connection.execute(
                "INSERT INTO applications (id, company, target_role, normalized_role, language, "
                "current_status, created_at, updated_at) "
                "VALUES ('b', 'Co', 'Role', 'Role', 'en', 'draft', '2026-01-01', '2026-01-01')"
            )
            raise RuntimeError("command refused after writing")

    with pytest.raises((KeyError, sqlite3.Error)):
        repository.get_application("b")

    with repository.unit_of_work() as unit:
        unit.connection.execute(
            "INSERT INTO applications (id, company, target_role, normalized_role, language, "
            "current_status, created_at, updated_at) "
            "VALUES ('c', 'Co', 'Role', 'Role', 'en', 'draft', '2026-01-01', '2026-01-01')"
        )
    with pytest.raises((KeyError, sqlite3.Error)):
        repository.get_application("c")


# --- commands take explicit sources; `latest` lives outside them --------------


def test_commands_require_owned_explicit_sources_and_compat_resolves_latest(engine) -> None:
    mine = engine.services.applications.ingest(IngestCommand(
        company="Mine Co", target_role="Account Manager", job_text=ACCOUNT_MANAGER_JOB
    ))
    theirs = engine.services.applications.ingest(IngestCommand(
        company="Theirs Co", target_role="Account Manager", job_text=ACCOUNT_MANAGER_JOB
    ))

    with pytest.raises(errors.LineageBroken, match="does not belong"):
        engine.services.analysis.analyze(AnalyzeCommand(
            application_id=mine.application_id,
            job_snapshot_id=theirs.job_snapshot_id,
        ))

    analysed = engine.services.analysis.analyze(AnalyzeCommand(
        application_id=theirs.application_id,
        job_snapshot_id=theirs.job_snapshot_id,
    ))
    with pytest.raises(errors.LineageBroken, match="does not belong"):
        engine.services.drafts.draft(DraftCommand(
            application_id=mine.application_id,
            job_analysis_id=analysed.analysis_id,
        ))
    ingested = engine.services.applications.ingest(IngestCommand(
        company="Legacy Co", target_role="Account Manager", job_text=ACCOUNT_MANAGER_JOB
    ))

    assert resolve_job_snapshot_id(engine.repo, ingested.application_id) == ingested.job_snapshot_id

    analysed = engine.services.analysis.analyze(AnalyzeCommand(
        application_id=ingested.application_id,
        job_snapshot_id=ingested.job_snapshot_id,
    ))
    assert resolve_job_analysis_id(engine.repo, ingested.application_id) == analysed.analysis_id
    from cv_engine.application.services import DraftService

    source = inspect.getsource(DraftService.draft)
    assert "latest_analysis" not in source
    assert source.count("latest_snapshot(") == 1
