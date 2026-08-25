from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import pytest
from api_harness import api_with_worker
from fake_provider import FakeOpenAI
from helpers import (
    ACCOUNT_MANAGER_JOB,
    AMBIGUOUS_HEBREW_JOB,
    CliRun,
    approve_active_draft,
    run_cli,
)
from seed import V2_IDENTITY_FACT, write_canonical_sources
from sqlalchemy import text
from sqlalchemy.engine import Engine

import cv_engine
from cv_engine.application.commands import (
    AnalyzeCommand,
    ApprovalResult,
    DraftCommand,
    IngestCommand,
)
from cv_engine.domain.analysis.classification import classify_job
from cv_engine.domain.candidate import contact_href
from cv_engine.domain.drafts import build_draft
from cv_engine.domain.facts import FactStore
from cv_engine.domain.models import (
    Emphasis,
    JobAnalysis,
    JobClassificationProposal,
    ProfileName,
    Track,
)
from cv_engine.domain.profiles import ProfileStore
from cv_engine.domain.render_validation import RenderEvidence, RenderGeometry
from cv_engine.domain.selection import EmphasisPolicyStore
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.infrastructure.knowledge import (
    FileKnowledge,
    load_candidate_context,
    load_emphasis_policies,
    load_fact_store,
    load_presentations,
    load_profile_store,
    seed_fact_before_workspace,
)
from cv_engine.infrastructure.persistence import (
    Repository,
    create_database_engine,
    current_database_revision,
)
from cv_engine.infrastructure.persistence.tables import metadata
from cv_engine.infrastructure.rendering import render_pdf, validate_rendered
from cv_engine.runtime.composition import Services, build_services
from cv_engine.runtime.config import resolve_config
from cv_engine.runtime.workspace import Workspace, create_workspace, load_workspace
from cv_engine.util import new_id

SOURCE_ROOT = Path(__file__).resolve().parent.parent


# The v1 worktree ships an editable install of this package, whose finder
# resolves any cv_engine submodule missing here to the v1 tree. Checking the
# top-level package is not enough: a single stale relative import is invisible
# that way, and every later result is then partly v1 code.
def _foreign_modules() -> dict[str, str]:
    return {
        name: cast(str, module.__file__)
        for name, module in sorted(sys.modules.items())
        if name.startswith("cv_engine")
        and getattr(module, "__file__", None)
        and SOURCE_ROOT not in Path(cast(str, module.__file__)).resolve().parents
    }


_IMPORTED_FROM = Path(cast(str, cv_engine.__file__)).resolve().parent.parent
assert _IMPORTED_FROM == SOURCE_ROOT, (
    f"tests import cv_engine from {_IMPORTED_FROM}, not the worktree under test ({SOURCE_ROOT})"
)
assert not _foreign_modules(), (
    f"cv_engine modules loaded from another worktree: {_foreign_modules()}"
)

# Only acceptance tests that validate real layout/PDF behavior use this fixture.
# Integrity tests create the same artifact/version graph with a deterministic
# renderer double, so Chromium is not paid for when the behavior under test is
# hashes, linkage, lifecycle, or database state.
BROWSER_FIXTURES = frozenset({"render_validator"})


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items) -> None:
    for item in items:
        if BROWSER_FIXTURES & set(item.fixturenames):
            item.add_marker("browser")


def pytest_sessionfinish(session, exitstatus) -> None:
    """Fail the run if any cv_engine module came from another worktree.

    Checked at the end as well as at import, because modules load lazily: a
    stale relative import inside a rarely exercised path would otherwise only
    show up as a mysteriously passing test.
    """
    foreign = _foreign_modules()
    if foreign:
        session.exitstatus = 1
        raise pytest.UsageError(f"cv_engine modules loaded from another worktree: {foreign}")


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
    services: Services
    application_id: str
    snapshot_id: str
    analysis_id: str | None = None
    selection_plan_id: str | None = None
    markdown: Path | None = None
    manifest: Path | None = None
    draft_report: Any = None
    approved: ApprovalResult | None = None
    pdf: Path | None = None
    ready_report: Any = None

    def __iter__(self):
        yield self.services
        yield self.application_id


@dataclass(frozen=True)
class DraftSetup:
    facts: FactStore
    profile: Any
    analysis: Any
    draft: Any
    markdown: Path | None
    candidate: Any = None

    def __iter__(self):
        yield self.facts
        yield self.profile
        yield self.analysis
        yield self.draft
        yield self.markdown


@dataclass(frozen=True)
class ProposalSetup:
    services: Services
    application_id: str
    analysis_id: str
    analysis: JobAnalysis
    payload: dict[str, Any]
    operation_id: str = ""

    def __iter__(self):
        yield self.services
        yield self.application_id
        yield self.analysis


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A marked, isolated test Workspace holding a full knowledge copy.

    The marker is part of the fixture because every normal command now opens
    its Workspace fail-closed; an unmarked directory is a guard test, not a
    starting point.
    """
    root = tmp_path / "repo"
    root.mkdir()
    write_canonical_sources(root / "base")
    # The identity fact and candidate context are added the way the product
    # adds them, rather than baked into the seed sources, so the fixture
    # exercises the real lifecycle instead of a shortcut around it.
    seed_fact_before_workspace(root / "base", "common.md", dict(V2_IDENTITY_FACT), canonical=True)
    shutil.copy2(SOURCE_ROOT / "base/candidate.json", root / "base/candidate.json")
    for name in ("profiles", "rendering", "ai", "config"):
        shutil.copytree(SOURCE_ROOT / name, root / name)
    create_workspace(root)
    return root


@pytest.fixture
def workspace(workspace_root: Path) -> Workspace:
    return load_workspace(workspace_root)


@pytest.fixture(scope="session")
def database_url() -> str:
    return str(resolve_config(env=os.environ).get("database_url"))


def alembic_head() -> str:
    """The single registered head, read from Alembic rather than pinned here.

    A literal revision in the test gate has to be edited by hand for every
    migration, and the edit is invisible until the whole database suite errors
    at setup. Deriving it means a new revision needs no change here at all.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(Config(str(SOURCE_ROOT / "alembic.ini"))).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Alembic must have exactly one head, found {heads}")
    return heads[0]


@pytest.fixture(scope="session")
def database_engine(database_url: str) -> Iterator[Engine]:
    engine = create_database_engine(database_url)
    head = alembic_head()
    if current_database_revision(engine) != head:
        engine.dispose()
        raise RuntimeError(
            f"test database is not at Alembic revision {head}; run "
            "'./.venv/bin/alembic upgrade head' first"
        )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def isolated_database(database_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test the same empty PostgreSQL schema and configured URL."""
    table_names = ", ".join(f'"{name}"' for name in metadata.tables)
    with database_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    monkeypatch.setenv(
        "CV_DATABASE_URL",
        database_engine.url.render_as_string(hide_password=False),
    )


@pytest.fixture
def fact_store(workspace_root: Path) -> FactStore:
    return load_fact_store(workspace_root / "base")


@pytest.fixture
def profile_store(workspace_root: Path, fact_store: FactStore) -> ProfileStore:
    return load_profile_store(workspace_root, fact_store)


@pytest.fixture
def policy_store(workspace_root: Path) -> EmphasisPolicyStore:
    return load_emphasis_policies(workspace_root)


@pytest.fixture
def presentation_store(workspace_root: Path, fact_store: FactStore):
    return load_presentations(workspace_root, fact_store)


@pytest.fixture
def candidate_context(workspace_root: Path, fact_store: FactStore):
    return load_candidate_context(workspace_root, fact_store)


@pytest.fixture
def services(workspace: Workspace) -> Services:
    return build_services(workspace)


@pytest.fixture
def task_contracts(workspace: Workspace):
    """The declared AI contracts, read the way every command reads them."""
    return FileKnowledge(workspace.knowledge_root, workspace_root=workspace.root).task_contracts()


@pytest.fixture
def fake_openai(monkeypatch) -> FakeOpenAI:
    """A scripted transport with the real adapter stack on top of it."""
    return FakeOpenAI().install(monkeypatch)


@pytest.fixture
def ai_services(workspace: Workspace, fake_openai: FakeOpenAI, task_contracts) -> Services:
    """Services whose AI provider is the real adapter over the fake transport.

    `OPENAI_API_KEY` stays unset. The key is handed to the adapter directly, so
    a test that forgets to script an answer fails on the missing script rather
    than reaching the network, and the offline guarantee is not weakened by the
    fixture that exercises AI.
    """
    return build_services(workspace, provider=fake_openai.provider(task_contracts))


@pytest.fixture
def application_repo(database_engine: Engine) -> Repository:
    return Repository(database_engine)


@pytest.fixture
def cli_runner(workspace_root: Path):
    """The CLI against the test Workspace, run in this process."""

    def run(*args: str) -> CliRun:
        return run_cli("--workspace", str(workspace_root), *args)

    return run


@pytest.fixture
def cli_subprocess(workspace_root: Path):
    """The CLI as a real process, for tests whose subject is that boundary."""

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cv_engine.cli", "--workspace", str(workspace_root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    return run


@pytest.fixture
def analyzed_application(services: Services):
    def build(
        company: str,
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        ingested = services.applications.ingest(
            IngestCommand(
                company=company,
                target_role=role,
                job_text=job_text,
                acknowledged_duplicates=True,
            )
        )
        analysed = services.analysis.analyze(
            AnalyzeCommand(
                application_id=ingested.application_id,
                job_snapshot_id=ingested.job_snapshot_id,
            )
        )
        return WorkflowSetup(
            services=services,
            application_id=ingested.application_id,
            snapshot_id=ingested.job_snapshot_id,
            analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )

    return build


@pytest.fixture
def drafted_application(analyzed_application):
    def build(
        company: str,
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = analyzed_application(company, role, job_text)
        assert setup.analysis_id is not None
        assert setup.selection_plan_id is not None
        drafted = setup.services.drafts.draft(
            DraftCommand(
                application_id=setup.application_id,
                job_analysis_id=setup.analysis_id,
                selection_plan_id=setup.selection_plan_id,
            )
        )
        paths = setup.services.artifacts.working_paths(setup.application_id)
        return replace(
            setup,
            markdown=paths.markdown,
            manifest=paths.manifest,
            draft_report=drafted.validation,
        )

    return build


@pytest.fixture
def approved_application(drafted_application):
    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = drafted_application(company, role, job_text)
        approved = approve_active_draft(setup.services, setup.application_id)
        return replace(setup, approved=approved)

    return build


@pytest.fixture
def deterministic_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render without Chromium, for tests whose subject is not the browser.

    Extracted from `ready_application` so the API tests can drive a render
    through HTTP and the Operation worker without paying for a browser. What is
    substituted is the same two module functions in both cases - the seam is
    `infrastructure.rendering`, not the port - so an API render exercises the
    identical service, handler, and registration path the CLI render does.

    Tests that are *about* rendering, PDF geometry, or ATS text use the
    `render_validator` fixture instead and are browser-marked by collection.
    """

    def render_without_browser(
        html_path: Path, pdf_path: Path, screenshot_path: Path
    ) -> dict[str, Any]:
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

    def deterministic_render_evidence(
        draft,
        _profile,
        html_path,
        pdf_path,
        screenshot_path,
        geometry,
        candidate,
        delivered_pdf_filename=None,
    ) -> RenderEvidence:
        extracted_text = "\n".join(
            [
                draft.headline.text,
                *(claim.text for claim in draft.contacts),
                *(claim.text for section in draft.sections for claim in section.claims),
            ]
        )
        links = [
            href
            for claim in draft.contacts
            if (href := contact_href(candidate, claim.fact_ids[0], claim.text)) is not None
        ]
        complete_geometry = {**geometry, "links": links}
        return RenderEvidence(
            html_path=str(html_path),
            html_exists=True,
            html_size=html_path.stat().st_size,
            html_text=html_path.read_text(encoding="utf-8"),
            pdf_path=str(pdf_path),
            pdf_name=delivered_pdf_filename or pdf_path.name,
            pdf_exists=True,
            pdf_size=pdf_path.stat().st_size,
            pdf_error=None,
            page_count=1,
            extracted_text=extracted_text,
            pdf_sha256="deterministic-integrity-double",
            screenshot_path=str(screenshot_path),
            screenshot_exists=True,
            screenshot_size=screenshot_path.stat().st_size,
            geometry=RenderGeometry(
                scroll_width=complete_geometry["scrollWidth"],
                client_width=complete_geometry["clientWidth"],
                scroll_height=complete_geometry["scrollHeight"],
                client_height=complete_geometry["clientHeight"],
                offenders=complete_geometry["offenders"],
                direction=complete_geometry["dir"],
                links=complete_geometry["links"],
                raw=complete_geometry,
            ),
        )

    monkeypatch.setattr("cv_engine.infrastructure.rendering.render_pdf", render_without_browser)
    monkeypatch.setattr(
        "cv_engine.infrastructure.rendering.collect_render_evidence",
        deterministic_render_evidence,
    )


@pytest.fixture
def ready_application(approved_application, deterministic_renderer):
    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = approved_application(company, role, job_text)
        rendered = setup.services.rendering.render(setup.application_id)
        pdf_record = setup.services.repository.latest_artifact_version(
            setup.application_id, "resume_pdf"
        )
        pdf = setup.services.artifacts.resolve(pdf_record["path"])
        assert rendered.validation.passed, rendered.validation.model_dump()
        assert (
            setup.services.repository.get_application(setup.application_id)["current_status"]
            == "saved"
        )
        assert setup.services.rendering.ready_qualification(setup.application_id).ready_qualified
        return replace(setup, pdf=pdf, ready_report=rendered.validation)

    return build


@pytest.fixture
def draft_factory(
    workspace_root: Path,
    fact_store: FactStore,
    profile_store: ProfileStore,
    policy_store: EmphasisPolicyStore,
    candidate_context,
):
    def build(
        job: str,
        *,
        application_id: str = "app-golden",
        job_snapshot_id: str = "snapshot-golden",
        job_analysis_id: str = "analysis-golden",
        write: bool = False,
        **overrides,
    ) -> DraftSetup:
        analysis = classify_job(job, **overrides)
        profile = profile_store.get(analysis.profile)
        draft = build_draft(
            application_id=application_id,
            job_snapshot_id=job_snapshot_id,
            job_analysis_id=job_analysis_id,
            analysis=analysis,
            profile=profile,
            facts=fact_store,
            policies=policy_store,
            candidate=candidate_context,
            presentations=load_presentations(workspace_root, fact_store),
        )
        store = FilesystemArtifactStore(load_workspace(workspace_root))
        markdown = store.write_working_draft(draft).paths.markdown if write else None
        return DraftSetup(fact_store, profile, analysis, draft, markdown, candidate_context)

    return build


@pytest.fixture
def classification_proposal():
    """Build what an AI provider may return for `classify_job`.

    Defaults are a confident, internally consistent Account Manager proposal, so
    each test only states the field it is actually probing.
    """

    def build(**overrides) -> JobClassificationProposal:
        return JobClassificationProposal(
            **{
                "track": Track.SALES,
                "profile": ProfileName.ACCOUNT_MANAGER,
                "emphasis": Emphasis.ACCOUNT_GROWTH,
                "confidence": 0.99,
                "rationale": "provider rationale",
                "gaps": [],
                "keywords": ["provider-keyword"],
                **overrides,
            }
        )

    return build


@pytest.fixture
def provider_analysis(ai_services: Services, fake_openai: FakeOpenAI):
    """Run one AI `propose_job_analysis` Operation end to end against the fake.

    It goes through the Operation runner rather than calling the service,
    because AI analysis has no synchronous form: the provider response has to
    be preserved against an Operation ID, and a test that bypassed the runner
    would be exercising a path the product does not have.
    """

    def run(
        response: JobClassificationProposal,
        *,
        job_text: str = AMBIGUOUS_HEBREW_JOB,
        company: str = "Provider Co",
        role: str = "Account Manager",
        **analyze_kwargs,
    ) -> ProposalSetup:
        fake_openai.script("propose_job_analysis", response)
        ingested = ai_services.applications.ingest(
            IngestCommand(
                company=company,
                target_role=role,
                job_text=job_text,
                acknowledged_duplicates=True,
            )
        )
        queued = ai_services.operations.submit_analysis(
            AnalyzeCommand(
                application_id=ingested.application_id,
                job_snapshot_id=ingested.job_snapshot_id,
                track_override=analyze_kwargs.pop("track", None),
                profile_override=analyze_kwargs.pop("profile", None),
                emphasis_override=analyze_kwargs.pop("emphasis", None),
                language_override=analyze_kwargs.pop("language", None),
                accept_low_fit=analyze_kwargs.pop("accept_low_fit", False),
                provider="openai",
                model="gpt-test",
                **analyze_kwargs,
            ),
            idempotency_key=new_id(),
            analysis_service=ai_services.analysis,
        )
        completed = ai_services.foreground_operations.execute(queued.id)
        if completed.status.value != "succeeded":
            raise AssertionError(
                f"analysis Operation failed: {completed.failure_code} "
                f"{completed.safe_failure_detail}"
            )
        outputs = {output.output_type: output.output_id for output in completed.outputs}
        analysis_id = outputs["job_analysis"]
        return ProposalSetup(
            services=ai_services,
            application_id=ingested.application_id,
            analysis_id=analysis_id,
            analysis=ai_services.repository.get_analysis(analysis_id)["analysis"],
            payload=fake_openai.calls_for("propose_job_analysis")[-1].payload,
            operation_id=completed.id,
        )

    return run


@pytest.fixture
def render_validator():
    def validate(draft, profile, html: Path, pdf: Path, screenshot: Path, candidate):
        geometry = render_pdf(html, pdf, screenshot)
        report = validate_rendered(draft, profile, html, pdf, screenshot, geometry, candidate)
        return geometry, report

    return validate


@pytest.fixture
def api_worker(services: Services):
    """The API and an Operation worker running together over one Workspace."""
    with api_with_worker(services) as harness:
        yield harness


@pytest.fixture
def ai_api_worker(ai_services: Services):
    """The same arrangement, with the AI provider wired to the fake transport."""
    with api_with_worker(ai_services) as harness:
        yield harness
