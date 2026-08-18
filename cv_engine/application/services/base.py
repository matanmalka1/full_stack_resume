from __future__ import annotations

from typing import Any, Generic, TypeVar

from ...domain.facts import FactStore
from ...domain.knowledge import Knowledge
from ...domain.models import (
    CandidateContext,
    DraftDocument,
    JobAnalysis,
    WorkingDraft,
)
from ...domain.profiles import ProfileStore
from ...domain.selection import EmphasisPolicyStore
from ..chain import ChainError, check_draft_chain
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    UnknownRecord,
)
from ..ports import (
    ArtifactStore,
    ClassificationProvider,
    KnowledgeStore,
    Renderer,
    RevisionPayloadStore,
)

RepoT = TypeVar("RepoT")


class ServiceBase(Generic[RepoT]):
    """Shared dependencies for the application services.

    Every service receives its collaborators explicitly and re-reads knowledge
    per command, so nothing here holds a cache that could disagree with the
    files a later command will read.
    """

    def __init__(
        self,
        *,
        repository: RepoT,
        knowledge: KnowledgeStore,
        artifacts: ArtifactStore,
        renderer: Renderer | None = None,
        provider: ClassificationProvider | None = None,
        snapshots: RevisionPayloadStore | None = None,
    ):
        self.repo = repository
        self.artifacts = artifacts
        self._knowledge = knowledge
        self._renderer = renderer
        self._provider = provider
        self._snapshots = snapshots

    def load_knowledge(self) -> Knowledge:
        try:
            return self._knowledge.load()
        except OSError as exc:
            raise InfrastructureFailure(f"could not read Knowledge: {exc}") from exc
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    def knowledge(self) -> tuple[FactStore, ProfileStore, EmphasisPolicyStore]:
        loaded = self.load_knowledge()
        return loaded.facts, loaded.profiles, loaded.policies

    def candidate(self) -> CandidateContext:
        return self.load_knowledge().candidate

    def fact_store(self) -> FactStore:
        try:
            return self._knowledge.facts()
        except OSError as exc:
            raise InfrastructureFailure(f"could not read facts: {exc}") from exc
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    @property
    def snapshot_payloads(self) -> RevisionPayloadStore:
        if self._snapshots is None:
            raise DependencyUnavailable(
                "this command needs the snapshot payload store and none was configured"
            )
        return self._snapshots

    @property
    def revision_payloads(self) -> RevisionPayloadStore:
        if self._snapshots is None:
            raise DependencyUnavailable(
                "this command needs the revision payload store and none was configured"
            )
        return self._snapshots

    def working_draft_record(self, application_id: str) -> WorkingDraft:
        try:
            return self.repo.active_working_draft(application_id)
        except KeyError as exc:
            raise UnknownRecord(f"no working draft for application: {application_id}") from exc

    def working_draft(self, application_id: str) -> DraftDocument:
        return self.working_draft_record(application_id).source

    def store_working_draft(self, draft: DraftDocument) -> Any:
        try:
            return self.artifacts.write_working_draft(draft)
        except OSError as exc:
            raise InfrastructureFailure(f"could not store working draft: {exc}") from exc

    def working_markdown(self, application_id: str) -> str:
        try:
            return self.artifacts.working_markdown(application_id)
        except OSError as exc:
            raise InfrastructureFailure(f"could not read working Markdown: {exc}") from exc

    def stored_draft(self, manifest_location: Any) -> DraftDocument:
        try:
            return self.artifacts.load_draft(manifest_location)
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not load stored draft: {exc}") from exc

    def artifact_text(self, location: Any) -> str:
        try:
            return self.artifacts.read_document(location)
        except OSError as exc:
            raise InfrastructureFailure(f"could not read stored artifact: {exc}") from exc

    def _bound_analysis(
        self,
        application_id: str,
        draft: DraftDocument,
        profiles: ProfileStore,
        facts: FactStore,
        *,
        recorded_analysis_id: str | None = None,
    ) -> tuple[str, JobAnalysis]:
        """The analysis this exact draft was built from, or a refusal.

        Called before any write on every path that consumes a draft, so a draft
        whose chain no longer holds is rejected while the working area, the
        artifact directory, and SQLite are all still untouched.
        """
        chain = check_draft_chain(
            self.repo,
            application_id,
            draft,
            profiles,
            facts,
            recorded_analysis_id=recorded_analysis_id,
        )
        try:
            return chain.bound()
        except ChainError as exc:
            raise LineageBroken(f"draft chain rejected: {exc}") from exc

    @property
    def renderer(self) -> Renderer:
        if self._renderer is None:
            raise DependencyUnavailable("this command needs a renderer and none was configured")
        return self._renderer
