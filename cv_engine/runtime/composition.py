from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..application.ports import ApplicationRepository, ClassificationProvider, KnowledgeStore, Renderer
from ..application.services import (
    AnalysisService,
    ApplicationService,
    DraftService,
    KnowledgeService,
    RenderingService,
    TrackingService,
)
from ..infrastructure.db import Repository
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
    applications: ApplicationService
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
    resolved_renderer = renderer or PlaywrightRenderer(workspace.knowledge_root)
    resolved_provider = provider or OpenAIClassificationProvider(
        workspace.knowledge_root / "ai" / "prompts" / "system-v1.md"
    )
    shared = {
        "repository": resolved_repository,
        "knowledge": resolved_knowledge,
        "workspace": workspace,
        "renderer": resolved_renderer,
        "provider": resolved_provider,
    }
    return Services(
        workspace=workspace,
        repository=resolved_repository,
        knowledge=resolved_knowledge,
        applications=ApplicationService(**shared),
        analysis=AnalysisService(**shared),
        drafts=DraftService(**shared),
        rendering=RenderingService(**shared),
        tracking=TrackingService(**shared),
        knowledge_lifecycle=KnowledgeService(**shared),
    )
