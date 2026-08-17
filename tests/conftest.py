from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from cv_engine.analysis import classify_job
from cv_engine.canonical_data import write_canonical_sources
from cv_engine.db import Repository, connect
from cv_engine.drafts import build_draft, write_working_draft
from cv_engine.facts import FactStore
from cv_engine.migration import create_snapshot, dry_run_migration, migrate_legacy_state, verify_snapshot
from cv_engine.models import (
    Emphasis,
    JobAnalysis,
    JobClassificationProposal,
    ProfileName,
    Track,
    ValidationReport,
)
from cv_engine.profiles import ProfileStore
from cv_engine.selection import EmphasisPolicyStore
from cv_engine.rendering import render_pdf, validate_rendered
from cv_engine.workflow import Engine
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB, seal_report


SOURCE_ROOT = Path(__file__).resolve().parent.parent

# Only acceptance tests that validate real layout/PDF behavior use this fixture.
# Integrity tests create the same artifact/version graph with a deterministic
# renderer double, so Chromium is not paid for when the behavior under test is
# hashes, linkage, lifecycle, or SQLite state.
BROWSER_FIXTURES = frozenset({"render_validator"})


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items) -> None:
    for item in items:
        if BROWSER_FIXTURES & set(item.fixturenames):
            item.add_marker("browser")


def pytest_collection_finish(session) -> None:
    """Guard against a reduced run being mistaken for a complete one.

    Rendering, PDF, and ATS checks are acceptance requirements, so an
    environment that claims completeness (CV_REQUIRE_BROWSER=1) must not
    silently drop them.
    """
    if not os.environ.get("CV_REQUIRE_BROWSER"):
        return
    if any(item.get_closest_marker("browser") for item in session.items):
        return
    raise pytest.UsageError(
        "CV_REQUIRE_BROWSER=1 but no browser tests were collected. "
        "Rendering/PDF/ATS coverage is required for a complete run; "
        'drop the "not browser" selection or unset CV_REQUIRE_BROWSER.'
    )


@dataclass(frozen=True)
class WorkflowSetup:
    engine: Engine
    application_id: str
    snapshot_id: str
    markdown: Path | None = None
    manifest: Path | None = None
    draft_report: Any = None
    approved: dict[str, Any] | None = None
    pdf: Path | None = None
    ready_report: Any = None

    def __iter__(self):
        yield self.engine
        yield self.application_id


@dataclass(frozen=True)
class DraftSetup:
    facts: FactStore
    profile: Any
    analysis: Any
    draft: Any
    markdown: Path | None

    def __iter__(self):
        yield self.facts
        yield self.profile
        yield self.analysis
        yield self.draft
        yield self.markdown


@dataclass(frozen=True)
class ProposalSetup:
    engine: Engine
    application_id: str
    analysis: JobAnalysis
    payload: dict[str, Any]

    def __iter__(self):
        yield self.engine
        yield self.application_id
        yield self.analysis


@dataclass(frozen=True)
class MigrationSetup:
    root: Path
    snapshot: Path

    def __iter__(self):
        yield self.root
        yield self.snapshot


@pytest.fixture
def v1_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    write_canonical_sources(root / "base")
    for name in ("profiles", "rendering", "ai", "config"):
        shutil.copytree(SOURCE_ROOT / name, root / name)
    return root


@pytest.fixture
def fact_store(v1_repo: Path) -> FactStore:
    return FactStore.load(v1_repo / "base")


@pytest.fixture
def profile_store(v1_repo: Path, fact_store: FactStore) -> ProfileStore:
    return ProfileStore.load(v1_repo, fact_store)


@pytest.fixture
def policy_store(v1_repo: Path) -> EmphasisPolicyStore:
    return EmphasisPolicyStore.load(v1_repo)


@pytest.fixture
def engine(v1_repo: Path) -> Engine:
    return Engine(v1_repo)


@pytest.fixture
def application_repo(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "applications.sqlite3")


@pytest.fixture
def cli_runner(v1_repo: Path):
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cv_engine.cli", "--repo", str(v1_repo), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    return run


@pytest.fixture
def analyzed_application(engine: Engine):
    def build(
        company: str,
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        application_id, snapshot_id = engine.ingest(company, role, job_text)
        engine.analyze(application_id)
        return WorkflowSetup(engine, application_id, snapshot_id)

    return build


@pytest.fixture
def drafted_application(analyzed_application):
    def build(
        company: str,
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = analyzed_application(company, role, job_text)
        markdown, manifest, report = setup.engine.draft(setup.application_id)
        return replace(setup, markdown=markdown, manifest=manifest, draft_report=report)

    return build


@pytest.fixture
def approved_application(drafted_application):
    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = drafted_application(company, role, job_text)
        approved = setup.engine.approve(setup.application_id)
        return replace(setup, approved=approved)

    return build


@pytest.fixture
def ready_application(approved_application, monkeypatch: pytest.MonkeyPatch):
    def render_without_browser(html_path: Path, pdf_path: Path, screenshot_path: Path) -> dict[str, Any]:
        pdf_path.write_bytes(b"%PDF-1.4\n% deterministic integrity-test artifact\n")
        screenshot_path.write_bytes(b"deterministic integrity-test visual evidence\n")
        html = html_path.read_text(encoding="utf-8")
        direction = "rtl" if '<html lang="he" dir="rtl">' in html else "ltr"
        return {
            "scrollWidth": 100,
            "clientWidth": 100,
            "scrollHeight": 100,
            "clientHeight": 100,
            "offenders": [],
            "dir": direction,
            "links": [],
        }

    def accept_deterministic_render(*_args, **_kwargs) -> ValidationReport:
        groups = {
            "render": True,
            "page_count": True,
            "pdf": True,
            "ats": True,
            "links": True,
            "visual": True,
            "direction": True,
            "filename": True,
        }
        return ValidationReport(
            passed=True,
            groups=groups,
            issues=[],
            evidence={"renderer": "deterministic-integrity-double", "page_count": 1},
        )

    monkeypatch.setattr("cv_engine.workflow.render_pdf", render_without_browser)
    monkeypatch.setattr("cv_engine.workflow.validate_rendered", accept_deterministic_render)

    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = approved_application(company, role, job_text)
        pdf, report = setup.engine.render(setup.application_id)
        assert report.passed, report.model_dump()
        assert setup.engine.repo.get_application(setup.application_id)["current_status"] == "ready"
        return replace(setup, pdf=pdf, ready_report=report)

    return build


@pytest.fixture
def draft_factory(
    v1_repo: Path,
    fact_store: FactStore,
    profile_store: ProfileStore,
    policy_store: EmphasisPolicyStore,
):
    def build(
        job: str,
        *,
        application_id: str = "app-golden",
        job_snapshot_id: str = "snapshot-golden",
        write: bool = False,
        **overrides,
    ) -> DraftSetup:
        analysis = classify_job(job, **overrides)
        profile = profile_store.get(analysis.profile)
        draft = build_draft(
            application_id=application_id,
            job_snapshot_id=job_snapshot_id,
            analysis=analysis,
            profile=profile,
            facts=fact_store,
            policies=policy_store,
        )
        markdown = write_working_draft(v1_repo, draft)[0] if write else None
        return DraftSetup(fact_store, profile, analysis, draft, markdown)

    return build


@pytest.fixture
def classification_proposal():
    """Build what an AI provider may return for `classify_job`.

    Defaults are a confident, internally consistent Account Manager proposal, so
    each test only states the field it is actually probing.
    """

    def build(**overrides) -> JobClassificationProposal:
        return JobClassificationProposal(**{
            "track": Track.SALES,
            "profile": ProfileName.ACCOUNT_MANAGER,
            "emphasis": Emphasis.ACCOUNT_GROWTH,
            "confidence": 0.99,
            "rationale": "provider rationale",
            "gaps": [],
            "keywords": ["provider-keyword"],
            **overrides,
        })

    return build


@pytest.fixture
def provider_analysis(engine: Engine, monkeypatch):
    """Run `Engine.analyze` end to end against a stubbed AI provider."""

    def run(
        response: JobClassificationProposal,
        *,
        job_text: str = AMBIGUOUS_HEBREW_JOB,
        company: str = "Provider Co",
        role: str = "Account Manager",
        **analyze_kwargs,
    ) -> ProposalSetup:
        captured: dict[str, Any] = {}

        class _StubProvider:
            name = "openai"

            def __init__(self, **_kwargs):
                pass

            def run(self, task, payload, output_model):
                assert task == "classify_job"
                assert output_model is JobClassificationProposal
                captured.update(payload)
                return response, None

        monkeypatch.setattr("cv_engine.workflow.OpenAIResponsesProvider", _StubProvider)
        application_id, _ = engine.ingest(company, role, job_text)
        _, analysis = engine.analyze(
            application_id, provider="openai", model="gpt-test", **analyze_kwargs
        )
        return ProposalSetup(engine, application_id, analysis, captured)

    return run


@pytest.fixture
def render_validator():
    def validate(draft, profile, html: Path, pdf: Path, screenshot: Path):
        geometry = render_pdf(html, pdf, screenshot)
        report = validate_rendered(draft, profile, html, pdf, screenshot, geometry)
        return geometry, report

    return validate


def _populate_legacy_repo(root: Path) -> None:
    (root / "jobs").mkdir(parents=True)
    (root / "docs").mkdir()
    shutil.copy2(SOURCE_ROOT / "docs/v1-migration-restore.md", root / "docs/v1-migration-restore.md")
    rows = [
        ["alpha", "account-manager", "", "outputs/alpha/cv-pdf/account-manager/Matan Malka - Account Manager.pdf", "draft", "2026-01-01", "", ""],
        ["beta", "developer", "https://example.test/job", "outputs/beta/cv-pdf/developer/Matan Malka - Full Stack Developer.pdf", "sent", "2026-01-02", "2026-01-03", "submitted"],
    ]
    with (root / "jobs/status.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["company", "role", "url", "cv_file", "status", "date_created", "date_sent", "notes"])
        writer.writerows(rows)
    for company, role, *_rest in rows:
        paths = [
            root / f"outputs/{company}/job-description/{company}_{role}.md",
            root / f"outputs/{company}/cv-drafts/cv_{company}_{role}.md",
            root / f"outputs/{company}/cv-drafts/cv_{company}_{role}.notes.md",
            root / f"outputs/{company}/cv-html/cv_{company}_{role}.html",
            root / rows[[row[0] for row in rows].index(company)][3],
        ]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((f"historical {company} {role} {path.suffix}\n").encode())
    base_paths = [
        root / "outputs/base/cv-drafts/cv_base_full-stack-developer.md",
        root / "outputs/base/cv-html/cv_base_full-stack-developer.html",
        root / "outputs/base/cv-pdf/full-stack-developer/Matan Malka - Full Stack Developer.pdf",
    ]
    for path in base_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"historical base\n")


def _write_passing_migration_test_report(root: Path) -> Path:
    target = root / "data/migration/migration-tests.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    report = seal_report({
        "passed": True,
        "command": ["python", "-m", "pytest", "tests/test_migration.py", "-q"],
        "returncode": 0,
        "stdout": "migration fixture passed",
        "stderr": "",
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


@pytest.fixture
def legacy_repo(tmp_path: Path) -> Path:
    root = tmp_path / "legacy"
    root.mkdir()
    _populate_legacy_repo(root)
    return root


@pytest.fixture
def migration_gate_repo(legacy_repo: Path) -> MigrationSetup:
    snapshot = create_snapshot(legacy_repo)
    dry_run_migration(legacy_repo, snapshot)
    _write_passing_migration_test_report(legacy_repo)
    return MigrationSetup(legacy_repo, snapshot)


@pytest.fixture
def completed_migration_repo(legacy_repo: Path) -> MigrationSetup:
    snapshot = create_snapshot(legacy_repo)
    verification = verify_snapshot(snapshot)
    report = migrate_legacy_state(legacy_repo, legacy_repo, dry_run=False)
    with connect(legacy_repo / "data/applications.sqlite3") as connection:
        connection.execute(
            "INSERT INTO migration_runs(id, snapshot_id, manifest_hash, dry_run_report_hash, "
            "row_count, artifact_count, report_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-migration-run",
                verification["snapshot_id"],
                verification["manifest_hash"],
                "fixture-dry-run-hash",
                report["application_count"],
                report["artifact_version_count"],
                "{}",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()
    return MigrationSetup(legacy_repo, snapshot)
