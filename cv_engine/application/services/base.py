from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from ...domain.facts import FactStore
from ...domain.knowledge import Knowledge
from ...domain.models import (
    CandidateContext,
    DraftDocument,
    JobAnalysis,
    ProviderTaskResult,
    WorkingDraft,
)
from ...domain.profiles import ProfileStore
from ...domain.selection import EmphasisPolicyStore
from ...util import new_id
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
    AIProvider,
    ArtifactRegistry,
    ArtifactStore,
    DraftRepository,
    KnowledgeStore,
    Renderer,
    RevisionPayloadStore,
    SnapshotPayload,
    WorkingDraftReader,
)
from .proposals import ProviderEvidence

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
        provider: AIProvider | None = None,
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

    @property
    def renderer(self) -> Renderer:
        if self._renderer is None:
            raise DependencyUnavailable("this command needs a renderer and none was configured")
        return self._renderer

    @property
    def provider(self) -> AIProvider:
        """The AI provider, or the refusal that names it as the missing piece.

        Refusing here rather than falling back is invariant 14: an AI command
        that quietly ran deterministically would hand back a result the user did
        not ask for, under provenance that says `deterministic`, with nothing to
        distinguish it from a run they chose. Continuing deterministically is a
        separate command the user issues.
        """
        if self._provider is None:
            raise DependencyUnavailable("AI mode was requested but no provider is configured")
        return self._provider

    def preserve(
        self,
        application_id: str,
        operation_id: str,
        task: str,
        provenance: ProviderTaskResult,
    ) -> ProviderEvidence:
        """Preserve and register one provider response, in the execute phase.

        **Registration happens here, not at activation.** A response registered
        inside the activation transaction does not exist at all when the
        Operation is cancelled or its sources moved between execution and
        activation - the payload is on disk with no `ArtifactVersion` naming it
        and no Operation output referring to it. Product specification §18
        requires the opposite: "a completed output after cancellation is
        recorded as inactive evidence".

        So the row is written in the same phase as the file it points at, and
        *activation* is expressed where the specification puts it - on the
        Operation output's `active` flag, which the runner sets only after a
        successful commit. Output existence and output activation are separate
        (§6 invariant 15), and this is the seam where they separate.

        There is exactly one `lifecycle_status`, `provider-output`. Whether the
        answer was used is already recorded twice - by the Operation's status
        and by its output's `active` flag - and a third copy in the artifact row
        would be a third thing that can disagree.
        """
        artifact_version_id, payload = self.preserve_provider_response(
            application_id, operation_id, provenance.sanitized_response
        )
        evidence = ProviderEvidence(
            task=task,
            artifact_version_id=artifact_version_id,
            payload=payload,
            provenance=provenance,
        )
        self.register_provider_response(cast(ArtifactRegistry, self.repo), application_id, evidence)
        return evidence

    def preserve_provider_response(
        self,
        application_id: str,
        operation_id: str,
        sanitized_response: str,
    ) -> tuple[str, SnapshotPayload]:
        """Write one sanitized provider response, before anything is registered.

        Filesystem first, database second - the order every immutable payload in
        this system uses. A registration that fails afterwards leaves a
        reconcilable orphan; a row written first would name content that does
        not exist.

        The artifact version ID is minted here because it is also the filename,
        so the registered row and the payload it points at are the same identity
        rather than two that have to be kept in step.
        """
        artifact_version_id = new_id()
        try:
            payload = self.revision_payloads.commit_provider_response(
                application_id,
                operation_id,
                artifact_version_id,
                sanitized_response,
            )
        except (OSError, ValueError, FileExistsError) as exc:
            raise InfrastructureFailure(f"could not preserve the provider response: {exc}") from exc
        return artifact_version_id, payload

    @staticmethod
    def register_provider_response(
        repository: ArtifactRegistry,
        application_id: str,
        evidence: ProviderEvidence,
    ) -> str:
        """Register one preserved response as an immutable artifact version.

        The metadata is provenance, not content: provider, model, contract,
        prompt, and input/output schema versions and hashes, response ID, usage,
        latency, and the three payload hashes. Never a key, never a header,
        never hidden reasoning - none of which exists in `ProviderContext` to
        occupy a field in the first place.
        """
        provenance = evidence.provenance
        metadata: dict[str, Any] = {
            "task": evidence.task,
            **provenance.context.model_dump(mode="json"),
            "input_hash": provenance.input_hash,
            "output_hash": provenance.output_hash,
            "raw_output_hash": provenance.raw_output_hash,
        }
        return repository.register_artifact_version(
            application_id,
            "provider_response",
            evidence.task,
            evidence.payload.reference,
            evidence.payload.sha256,
            "provider-output",
            metadata=metadata,
            artifact_version_id=evidence.artifact_version_id,
        )


def working_draft_record(repo: WorkingDraftReader, application_id: str) -> WorkingDraft:
    """The application's active working draft, or a refusal naming it.

    A free function rather than a `ServiceBase` method: the repository it needs
    is `WorkingDraftReader`, and taking it as an argument is what makes each
    caller declare a port that actually supplies it.
    """
    try:
        return repo.active_working_draft(application_id)
    except UnknownRecord as exc:
        raise UnknownRecord(f"no working draft for application: {application_id}") from exc


def working_draft_document(repo: WorkingDraftReader, application_id: str) -> DraftDocument:
    return working_draft_record(repo, application_id).source


def bound_analysis(
    repo: DraftRepository,
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
    artifact directory, and database are all still untouched.
    """
    chain = check_draft_chain(
        repo,
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
