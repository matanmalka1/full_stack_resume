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

from cv_engine.application import errors
from cv_engine.application.commands import (
    AnalysisResult,
    ApprovalResult,
    DraftResult,
    IngestedApplication,
)
from cv_engine.application.ports import (
    ApplicationRepository,
    ApplicationStore,
    ArtifactRegistry,
    FactAudit,
    JobStore,
    UnitOfWork,
)
from cv_engine.application.services import AnalysisService, DraftService, RenderingService
from cv_engine.compat import resolve_job_analysis_id, resolve_job_snapshot_id
from cv_engine.infrastructure.db import Repository
from helpers import ACCOUNT_MANAGER_JOB


# --- results are typed, not positional --------------------------------------


def test_commands_answer_with_named_results(engine) -> None:
    services = engine.services

    ingested = services.applications.ingest(
        "Named Co", "Account Manager", ACCOUNT_MANAGER_JOB
    )
    assert isinstance(ingested, IngestedApplication)

    analysed = services.analysis.analyze(
        ingested.application_id, ingested.job_snapshot_id
    )
    assert isinstance(analysed, AnalysisResult)
    assert analysed.analysis.track.value

    drafted = services.drafts.draft(ingested.application_id, analysed.analysis_id)
    assert isinstance(drafted, DraftResult)
    assert drafted.markdown.is_file() and drafted.manifest.is_file()
    assert drafted.validation.passed, drafted.validation.model_dump()

    approved = services.drafts.approve(ingested.application_id)
    assert isinstance(approved, ApprovalResult)
    assert approved.version == 1


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


# --- commands take explicit sources; `latest` lives outside them --------------


def test_commands_require_owned_explicit_sources_and_compat_resolves_latest(engine) -> None:
    assert "job_snapshot_id" in inspect.signature(AnalysisService.analyze).parameters
    assert "job_analysis_id" in inspect.signature(DraftService.draft).parameters
    mine = engine.services.applications.ingest("Mine Co", "Account Manager", ACCOUNT_MANAGER_JOB)
    theirs = engine.services.applications.ingest("Theirs Co", "Account Manager", ACCOUNT_MANAGER_JOB)

    with pytest.raises(errors.LineageBroken, match="does not belong"):
        engine.services.analysis.analyze(mine.application_id, theirs.job_snapshot_id)

    analysed = engine.services.analysis.analyze(theirs.application_id, theirs.job_snapshot_id)
    with pytest.raises(errors.LineageBroken, match="does not belong"):
        engine.services.drafts.draft(mine.application_id, analysed.analysis_id)
    ingested = engine.services.applications.ingest("Legacy Co", "Account Manager", ACCOUNT_MANAGER_JOB)

    assert resolve_job_snapshot_id(engine.repo, ingested.application_id) == ingested.job_snapshot_id

    analysed = engine.services.analysis.analyze(ingested.application_id, ingested.job_snapshot_id)
    assert resolve_job_analysis_id(engine.repo, ingested.application_id) == analysed.analysis_id
    source = (Path(inspect.getfile(DraftService))).read_text(encoding="utf-8")
    assert "latest_analysis" not in source
    assert source.count("latest_snapshot(") == 1
