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
    EditResult,
    IngestedApplication,
    RenderResult,
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


def test_rendering_answers_with_a_named_result(approved_application, ready_application) -> None:
    # `ready_application` is requested for its deterministic renderer doubles;
    # a freshly approved application is rendered here so the assertion sees the
    # service's own result rather than one the fixture already unwrapped.
    setup = approved_application("Rendered Co")

    rendered = setup.engine.services.rendering.render(setup.application_id)

    assert isinstance(rendered, RenderResult)
    assert rendered.pdf.is_file()


def test_a_claim_edit_answers_with_a_named_result(drafted_application) -> None:
    setup = drafted_application("Edit Co")
    engine, application_id = setup
    claim = next(
        claim
        for section in engine.services.artifacts.load_working_draft(application_id).sections
        for claim in section.claims
    )

    edited = engine.services.drafts.edit_claim(
        application_id, claim.claim_id, claim.fact_ids, text=claim.text
    )

    assert isinstance(edited, EditResult)
    assert edited.markdown.is_file()


# --- refusals are typed -----------------------------------------------------


def test_every_refusal_is_an_application_error() -> None:
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


def test_the_v1_workflow_error_still_catches_the_whole_taxonomy() -> None:
    assert errors.WorkflowError is errors.ApplicationError


def test_a_missing_renderer_is_a_dependency_refusal(engine) -> None:
    """A command that needs a collaborator it was not given says which one."""
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


@pytest.mark.parametrize("port", [ApplicationStore, JobStore, ArtifactRegistry, FactAudit])
def test_the_sqlite_adapter_satisfies_each_focused_port(port, tmp_path: Path) -> None:
    repository = Repository(tmp_path / "applications.sqlite3")
    for name in port.__protocol_attrs__:
        assert callable(getattr(repository, name)), name


def test_the_repository_port_exposes_no_connection_or_path() -> None:
    """A service that can reach the database directly is not behind a port."""
    leaked = {"path", "transaction", "connection"} & set(ApplicationRepository.__protocol_attrs__)
    assert not leaked, leaked
    private = {name for name in ApplicationRepository.__protocol_attrs__ if name.startswith("_")}
    assert not private, private


# --- the unit of work is a real boundary -------------------------------------


def test_the_unit_of_work_commits_what_it_wraps(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "applications.sqlite3")
    with repository.unit_of_work() as unit:
        assert isinstance(unit, UnitOfWork)
        unit.connection.execute(
            "INSERT INTO applications (id, company, target_role, normalized_role, language, "
            "current_status, created_at, updated_at) "
            "VALUES ('a', 'Co', 'Role', 'Role', 'en', 'draft', '2026-01-01', '2026-01-01')"
        )

    assert repository.get_application("a")["company"] == "Co"


def test_the_unit_of_work_rolls_back_a_failed_command(tmp_path: Path) -> None:
    """Nothing a refused command wrote survives it."""
    repository = Repository(tmp_path / "applications.sqlite3")
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


def test_commands_take_explicit_source_ids() -> None:
    """Architecture §8: `latest` is query convenience, not command semantics."""
    assert "job_snapshot_id" in inspect.signature(AnalysisService.analyze).parameters
    assert "job_analysis_id" in inspect.signature(DraftService.draft).parameters


def test_a_source_from_another_application_is_refused(engine) -> None:
    """An explicit ID is only worth taking if it is checked."""
    mine = engine.services.applications.ingest("Mine Co", "Account Manager", ACCOUNT_MANAGER_JOB)
    theirs = engine.services.applications.ingest("Theirs Co", "Account Manager", ACCOUNT_MANAGER_JOB)

    with pytest.raises(errors.LineageBroken, match="does not belong"):
        engine.services.analysis.analyze(mine.application_id, theirs.job_snapshot_id)

    analysed = engine.services.analysis.analyze(theirs.application_id, theirs.job_snapshot_id)
    with pytest.raises(errors.LineageBroken, match="does not belong"):
        engine.services.drafts.draft(mine.application_id, analysed.analysis_id)


def test_the_compatibility_layer_is_what_resolves_latest(engine) -> None:
    """A v1 signature carries no source ID, so the resolver supplies one."""
    ingested = engine.services.applications.ingest("Legacy Co", "Account Manager", ACCOUNT_MANAGER_JOB)

    assert resolve_job_snapshot_id(engine.repo, ingested.application_id) == ingested.job_snapshot_id

    analysed = engine.services.analysis.analyze(ingested.application_id, ingested.job_snapshot_id)
    assert resolve_job_analysis_id(engine.repo, ingested.application_id) == analysed.analysis_id


def test_no_command_resolves_its_own_source(engine) -> None:
    """`latest_analysis` may not appear in a command's body at all.

    `latest_snapshot` survives in `draft` as a staleness check on the analysis
    the caller named, which is a guard rather than a choice of source, so it is
    asserted to appear exactly once and only there.
    """
    source = (Path(inspect.getfile(DraftService))).read_text(encoding="utf-8")
    assert "latest_analysis" not in source
    assert source.count("latest_snapshot(") == 1
