from __future__ import annotations

import json as _json
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic, sleep
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest
from api_harness import api_with_worker
from fake_provider import FakeOpenAI
from fastapi.testclient import TestClient
from foreground import foreground_executor
from helpers import (
    ACCOUNT_MANAGER_JOB,
    AMBIGUOUS_HEBREW_JOB,
    approve_active_draft,
)
from seed import V2_IDENTITY_FACT, write_canonical_sources
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError

import cv_engine
from cv_engine.api.app import API_PREFIX, create_app
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
    seed_fact_before_project,
)
from cv_engine.infrastructure.persistence import (
    Repository,
    create_database_engine,
    current_database_revision,
)
from cv_engine.infrastructure.persistence.tables import metadata
from cv_engine.infrastructure.rendering import render_pdf, validate_rendered
from cv_engine.runtime.composition import Services, build_api_services, build_services
from cv_engine.runtime.config import resolve_config
from cv_engine.runtime.paths import AppPaths
from cv_engine.util import new_id

SOURCE_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent


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
def project_root(tmp_path: Path) -> Path:
    """An isolated application root holding a full knowledge copy."""
    root = tmp_path / "repo"
    root.mkdir()
    write_canonical_sources(root / "base")
    # The identity fact and candidate context are added the way the product
    # adds them, rather than baked into the seed sources, so the fixture
    # exercises the real lifecycle instead of a shortcut around it.
    seed_fact_before_project(root / "base", "common.md", dict(V2_IDENTITY_FACT), canonical=True)
    shutil.copy2(SOURCE_ROOT / "base/candidate.json", root / "base/candidate.json")
    for name in ("profiles", "rendering", "ai", "config"):
        shutil.copytree(SOURCE_ROOT / name, root / name)
    return root


@pytest.fixture
def app_paths(project_root: Path) -> AppPaths:
    """The test project's paths, injected rather than selected by environment."""
    return AppPaths.from_root(project_root)


#: The suffix that marks a database as the suite's own. Test-plan 2.3 requires an
#: isolated database, and every fixture here TRUNCATEs the whole schema, so a URL
#: that is not marked is refused rather than emptied.
TEST_DATABASE_SUFFIX = "_test"


def _isolated_database_url(configured: str) -> str:
    """Derive the suite's database from the configured one, never reusing it.

    The suite used to read `database_url` straight from the config contract, so
    with nothing set it ran against the runtime default (`.../cv`) - the
    developer's own database - and `isolated_database` TRUNCATEs at setup while
    leaving the last test's rows behind. That is how ten `artifact_versions`
    rows pointing into a deleted pytest tmp root ended up in a running system,
    where reconcile correctly reported ten missing payloads.

    Deriving the name means the default is safe with nothing configured;
    `CV_TEST_DATABASE_URL` overrides it, and an override that names the
    configured runtime database is refused instead of honoured.
    """
    url = make_url(configured)
    override = os.environ.get("CV_TEST_DATABASE_URL")
    if override:
        candidate = make_url(override)
        if (candidate.host, candidate.port, candidate.database) == (
            url.host,
            url.port,
            url.database,
        ):
            raise RuntimeError(
                "CV_TEST_DATABASE_URL names the configured runtime database "
                f"({url.database!r}); the suite truncates every table, so it "
                "must point at a separate database"
            )
        return candidate.render_as_string(hide_password=False)
    name = url.database or ""
    if not name.endswith(TEST_DATABASE_SUFFIX):
        name = f"{name}{TEST_DATABASE_SUFFIX}"
    return url.set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def database_url() -> str:
    return _isolated_database_url(str(resolve_config(env=os.environ).get("database_url")))


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
    try:
        revision = current_database_revision(engine)
    except OperationalError as error:
        engine.dispose()
        raise RuntimeError(
            f"the isolated test database {engine.url.database!r} is unreachable; "
            "create it once with "
            f"'docker compose exec postgres createdb -U cv {engine.url.database}' "
            "and migrate it with "
            f"'CV_DATABASE_URL={engine.url.render_as_string(hide_password=False)} "
            "./.venv/bin/alembic upgrade head'"
        ) from error
    if revision != head:
        engine.dispose()
        raise RuntimeError(
            f"test database {engine.url.database!r} is not at Alembic revision {head}; run "
            f"'CV_DATABASE_URL={engine.url.render_as_string(hide_password=False)} "
            "./.venv/bin/alembic upgrade head' first"
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
def fact_store(project_root: Path) -> FactStore:
    return load_fact_store(project_root / "base")


@pytest.fixture
def profile_store(project_root: Path, fact_store: FactStore) -> ProfileStore:
    return load_profile_store(project_root, fact_store)


@pytest.fixture
def policy_store(project_root: Path) -> EmphasisPolicyStore:
    return load_emphasis_policies(project_root)


@pytest.fixture
def presentation_store(project_root: Path, fact_store: FactStore):
    return load_presentations(project_root, fact_store)


@pytest.fixture
def candidate_context(project_root: Path, fact_store: FactStore):
    return load_candidate_context(project_root, fact_store)


@pytest.fixture
def services(app_paths: AppPaths) -> Services:
    return build_services(app_paths)


@pytest.fixture
def task_contracts(app_paths: AppPaths):
    """The declared AI contracts, read the way every command reads them."""
    return FileKnowledge(app_paths.knowledge_root, project_root=app_paths.root).task_contracts()


@pytest.fixture
def fake_openai(monkeypatch) -> FakeOpenAI:
    """A scripted transport with the real adapter stack on top of it."""
    return FakeOpenAI().install(monkeypatch)


@pytest.fixture
def ai_services(app_paths: AppPaths, fake_openai: FakeOpenAI, task_contracts) -> Services:
    """Services whose AI provider is the real adapter over the fake transport.

    `OPENAI_API_KEY` stays unset. The key is handed to the adapter directly, so
    a test that forgets to script an answer fails on the missing script rather
    than reaching the network, and the offline guarantee is not weakened by the
    fixture that exercises AI.
    """
    return build_services(app_paths, provider=fake_openai.provider(task_contracts))


@pytest.fixture
def application_repo(database_engine: Engine) -> Repository:
    return Repository(database_engine)


@dataclass(frozen=True)
class HttpReply:
    status: int
    body: str

    @property
    def json(self) -> Any:
        return _json.loads(self.body)


class LiveApiServer:
    """A real uvicorn process, addressed over a socket.

    The in-process API tests share a composition root with the code they test.
    This does not: every call leaves the test process, so what it proves is
    that state is durable rather than held in a live object graph.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def _call(self, method: str, path: str, body: Any = None) -> HttpReply:
        data = _json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if method != "GET":
            # The origin policy refuses a state-changing request that does not
            # declare where it came from; a browser always sends one.
            headers["Origin"] = self.base_url
        request = Request(
            f"{self.base_url}{API_PREFIX}{path}", data=data, method=method, headers=headers
        )
        try:
            with urlopen(request, timeout=30) as response:
                return HttpReply(response.status, response.read().decode())
        except HTTPError as error:
            return HttpReply(error.code, error.read().decode())
        except URLError as error:
            # Not yet listening: the readiness poll asks before the socket is
            # bound, and a refused connection is an answer, not a crash.
            return HttpReply(0, str(error))

    def get(self, path: str, params: dict[str, str] | None = None) -> HttpReply:
        query = f"?{urlencode(params)}" if params else ""
        return self._call("GET", f"{path}{query}")

    def post(self, path: str, body: Any) -> HttpReply:
        return self._call("POST", path, body)


@pytest.fixture
def live_api_server(project_root: Path, database_url: str) -> Iterator[LiveApiServer]:
    """Serve the API from a separate process against the isolated project."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        # `asgi_factory` rather than the production entry point: the root is not
        # selectable at runtime, so a test project needs its own composition.
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "asgi_factory:build_test_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(TESTS_DIR),
        env={
            **os.environ,
            "CV_TEST_ASGI_ROOT": str(project_root),
            "CV_DATABASE_URL": database_url,
            "PYTHONPATH": str(TESTS_DIR),
            # The app has to know the port it answers on, or its own origin
            # is not the one it allows.
            "CV_API_PORT": str(port),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    server = LiveApiServer(f"http://127.0.0.1:{port}")
    try:
        deadline = monotonic() + 60
        while monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"API process exited early:\n{process.stdout.read()}")
            if server.get("/health").status == 200:
                break
            sleep(0.1)
        else:
            pytest.fail("API process did not become ready")
        yield server
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


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
                client="web",
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
    identical service, handler, and registration path the worker render uses.

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
    project_root: Path,
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
            presentations=load_presentations(project_root, fact_store),
        )
        store = FilesystemArtifactStore(AppPaths.from_root(project_root))
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
                client="web",
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
        completed = foreground_executor(ai_services).execute(queued.id)
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
    """The API and an Operation worker running together over one project."""
    with api_with_worker(services) as harness:
        yield harness


@dataclass(frozen=True)
class PausedApiHarness:
    """The API with nothing executing its queue, and a way to run one Operation.

    The worker-backed harness is right for almost everything: a `202` only means
    something if something drains the queue. It is the wrong tool for the window between
    the `202` and the write, because racing a live worker thread makes the assertion a
    coin flip. Here nothing runs until `run_operation` is called, so a test can put an
    edit or an archive squarely inside that window and know it landed there.
    """

    client: Any
    services: Services

    def run_operation(self, operation_id: str) -> dict[str, Any]:
        """Execute one queued Operation here, in the calling thread."""
        finished = foreground_executor(self.services).execute(operation_id)
        return finished.model_dump(mode="json")

    #: The worker-backed harness' method name, so the setup helpers shared with the
    #: worker-backed tests work unchanged. There it waits for a worker to reach a
    #: terminal status; here nothing would ever reach one on its own, so waiting *is*
    #: running. Only the Operation a test deliberately leaves queued stays queued.
    wait_for_operation = run_operation


@pytest.fixture
def api_paused(services: Services):
    """The API with no worker: Operations queue and stay queued until driven."""
    with TestClient(create_app(build_api_services(services))) as client:
        yield PausedApiHarness(client=client, services=services)


@pytest.fixture
def ai_api_worker(ai_services: Services):
    """The same arrangement, with the AI provider wired to the fake transport."""
    with api_with_worker(ai_services) as harness:
        yield harness
