from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fake_provider import FakeOpenAI
from seed import V2_IDENTITY_FACT, write_canonical_sources

from cv_engine.domain.analysis.requirements.concepts import RequirementConceptStore
from cv_engine.domain.contracts.analysis import JobAnalysis
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.domain.drafts import build_draft
from cv_engine.domain.facts import FactStore
from cv_engine.domain.profiles import ProfileStore
from cv_engine.domain.selection import EmphasisPolicyStore
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.infrastructure.knowledge import (
    FileKnowledge,
    load_candidate_context,
    load_emphasis_policies,
    load_fact_store,
    load_presentations,
    load_profile_store,
    load_requirement_concepts,
    seed_fact_before_project,
)
from cv_engine.runtime.composition import Services, build_services
from cv_engine.runtime.paths import AppPaths

from fixtures.models import DraftSetup

SOURCE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """An isolated application root holding a full knowledge copy."""
    root = tmp_path / "repo"
    root.mkdir()
    write_canonical_sources(root / "base")
    seed_fact_before_project(root / "base", "common.json", dict(V2_IDENTITY_FACT), canonical=True)
    shutil.copy2(SOURCE_ROOT / "base/candidate.json", root / "base/candidate.json")
    for name in ("profiles", "rendering", "ai", "config"):
        shutil.copytree(SOURCE_ROOT / name, root / name)
    return root


@pytest.fixture
def app_paths(project_root: Path) -> AppPaths:
    return AppPaths.from_root(project_root)


@pytest.fixture
def fact_store(project_root: Path) -> FactStore:
    return load_fact_store(project_root / "base")


@pytest.fixture
def requirement_concepts(project_root: Path) -> RequirementConceptStore:
    return load_requirement_concepts(project_root)


@pytest.fixture
def analysis_document(
    fact_store: FactStore,
    profile_store: ProfileStore,
    requirement_concepts: RequirementConceptStore,
):
    def _analysis_document(**overrides):
        profile = ProfileName(overrides.pop("profile_override", None) or "development")
        selected = profile_store.get(profile)
        emphasis = Emphasis(overrides.pop("emphasis_override", None) or selected.default_emphasis)
        language = overrides.pop("language_override", None) or "en"
        return JobAnalysis(
            track=Track(overrides.pop("track_override", None) or selected.track),
            profile=profile,
            emphasis=emphasis,
            language=language,
            summary="test analysis fixture",
            **overrides,
        )

    return _analysis_document


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
    return FileKnowledge(app_paths.knowledge_root, project_root=app_paths.root).task_contracts()


@pytest.fixture
def fake_openai(monkeypatch) -> FakeOpenAI:
    return FakeOpenAI().install(monkeypatch)


@pytest.fixture
def ai_services(app_paths: AppPaths, fake_openai: FakeOpenAI, task_contracts) -> Services:
    return build_services(app_paths, provider=fake_openai.provider(task_contracts))


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
        profile_name = ProfileName(overrides.pop("profile_override", None) or "account-manager")
        profile = profile_store.get(profile_name)
        removed = sorted(set(overrides) & {"fit", "fit_score", "gaps", "confidence", "rationale"})
        if removed:
            raise TypeError(
                f"draft_factory no longer accepts {removed}: state them as requirements"
            )
        analysis = JobAnalysis(
            track=Track(overrides.pop("track_override", None) or profile.track),
            profile=profile_name,
            emphasis=Emphasis(overrides.pop("emphasis_override", None) or profile.default_emphasis),
            language=overrides.pop("language_override", "en"),
            summary="test analysis fixture",
            keywords=overrides.pop("keywords", []),
            requirements=overrides.pop("requirements", []),
            **overrides,
        )
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
