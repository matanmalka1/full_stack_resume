from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..application.ports import (
    ApplicationRepository,
    ArtifactStore,
    ClassificationProvider,
    KnowledgeStore,
    Renderer,
    UnitOfWork,
)
from ..application.services.analysis import AnalysisService
from ..application.services.applications import ApplicationService
from ..application.services.drafts import DraftService
from ..application.services.knowledge import KnowledgeService
from ..application.services.projections import ApplicationQueryService
from ..application.services.rendering import RenderingService
from ..application.services.tracking import TrackingService
from ..infrastructure.artifacts import FilesystemArtifactStore
from ..infrastructure.persistence import Repository
from ..infrastructure.knowledge import FileKnowledge
from ..infrastructure.providers import OpenAIClassificationProvider
from ..infrastructure.rendering import PlaywrightRenderer
from .workspace import Workspace


@dataclass(frozen=True)
class Services:
    """Everything a client needs, already wired to one Workspace."""

    workspace: Workspace
    repository: ApplicationRepository
    knowledge: KnowledgeStore
    artifacts: ArtifactStore
    unit_of_work: Callable[[], UnitOfWork]
    applications: ApplicationService
    queries: ApplicationQueryService
    analysis: AnalysisService
    drafts: DraftService
    rendering: RenderingService
    tracking: TrackingService
    knowledge_lifecycle: KnowledgeService


def build_services(
    workspace: Workspace,
    *,
    database_path: Path | None = None,
    repository: ApplicationRepository | None = None,
    knowledge: KnowledgeStore | None = None,
    artifacts: ArtifactStore | None = None,
    renderer: Renderer | None = None,
    provider: ClassificationProvider | None = None,
) -> Services:
    """The manual composition root.

    The only place that decides which concrete adapter satisfies which port.
    Callers may substitute any of them — that is how tests replace the browser
    and the AI provider without the application layer knowing either exists.
    """
    resolved_repository = repository or Repository(database_path or workspace.database_path)
    resolved_knowledge = knowledge or FileKnowledge(workspace.knowledge_root)
    resolved_artifacts = artifacts or FilesystemArtifactStore(workspace)
    resolved_renderer = renderer or PlaywrightRenderer(workspace.knowledge_root)
    resolved_provider = provider or OpenAIClassificationProvider(
        workspace.knowledge_root / "ai" / "prompts" / "system-v1.md"
    )
    shared = {
        "repository": resolved_repository,
        "knowledge": resolved_knowledge,
        "artifacts": resolved_artifacts,
        "renderer": resolved_renderer,
        "provider": resolved_provider,
    }
    return Services(
        workspace=workspace,
        repository=resolved_repository,
        knowledge=resolved_knowledge,
        artifacts=resolved_artifacts,
        unit_of_work=resolved_repository.unit_of_work,
        applications=ApplicationService(**shared),
        queries=ApplicationQueryService(**shared),
        analysis=AnalysisService(**shared),
        drafts=DraftService(**shared),
        rendering=RenderingService(**shared),
        tracking=TrackingService(**shared),
        knowledge_lifecycle=KnowledgeService(**shared),
    )
