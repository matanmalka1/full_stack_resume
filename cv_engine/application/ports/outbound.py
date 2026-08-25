"""What the application calls out to: files, knowledge, rendering, AI.

These are not repositories. They are the effects the application cannot
perform itself, declared as protocols so the deterministic workflow can run
against local adapters with no AI key present.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from ...domain.knowledge import Knowledge
from ...domain.models import (
    CandidateContext,
    ClaimProposal,
    DraftDocument,
    DraftProposal,
    JobClassificationProposal,
    Profile,
    ProviderTaskResult,
    SectionProposal,
    SelectionProposal,
    StrictModel,
    ValidationReport,
)
from ..knowledge_mutations import (
    KnowledgeFileState,
    KnowledgeMutation,
    StagedKnowledgeFile,
)
from .values import (
    ArtifactStream,
    DraftPaths,
    RenderTargets,
    RevisionPayloads,
    SnapshotPayload,
    StoredDraft,
    TaskContracts,
)


class ArtifactStore(Protocol):
    """Where immutable and working payloads live.

    The application layer asks for "this application's working draft" or "this
    approved version"; it never composes a directory name and never opens a
    file. That is what keeps the storage layout an infrastructure decision
    instead of a rule spread across services.
    """

    def working_paths(self, application_id: str) -> DraftPaths: ...

    def write_working_draft(self, draft: Any) -> StoredDraft: ...

    def load_working_draft(self, application_id: str) -> Any: ...

    def working_markdown(self, application_id: str) -> str: ...

    def read_document(self, path: Path) -> str: ...

    def load_draft(self, manifest_path: Path) -> Any: ...

    def paths_beside(self, manifest_path: Path) -> DraftPaths: ...

    def approved_version_dir(self, application_id: str, version: int) -> Path: ...

    def publish_working_draft(self, application_id: str, version: int) -> DraftPaths: ...

    def resolve(self, stored_path: str) -> Path: ...

    def relative(self, path: Path) -> str: ...


class SnapshotPayloadStore(Protocol):
    def commit_snapshot(
        self,
        application_id: str,
        snapshot_id: str,
        text: str,
    ) -> SnapshotPayload: ...

    def read_snapshot(self, reference: str, expected_hash: str) -> str: ...

    def read_payload_text(self, reference: str) -> str:
        """Return one registered immutable payload as text.

        For a caller that has already verified the payload's hash and needs its
        content - Ready qualification re-deriving draft bindings from a claim
        manifest. `read_snapshot` refuses anything that is not a JobSnapshot,
        and `open_artifact` is the outward-facing download path.
        """
        ...

    def verify_payload(self, reference: str, expected_hash: str) -> str:
        """Classify one registered payload without transferring it outward.

        Returns `ok`, `missing`, `tampered`, or `unresolvable`. Ready
        qualification uses this to re-derive itself from stored evidence:
        resolving a reference to a local path and hashing the file verified the
        filesystem rather than the configured store, and reported everything
        missing once storage moved off local disk.
        """
        ...

    def open_artifact(self, reference: str, expected_hash: str) -> ArtifactStream: ...


class RevisionPayloadStore(SnapshotPayloadStore, Protocol):
    def commit_revision(
        self,
        application_id: str,
        revision_id: str,
        structured_json: str,
        markdown: str,
    ) -> RevisionPayloads: ...

    def commit_draft_snapshot(
        self,
        application_id: str,
        working_draft_id: str,
        edit_version: int,
        structured_json: str,
    ) -> SnapshotPayload: ...

    def commit_provider_response(
        self,
        application_id: str,
        operation_id: str,
        artifact_id: str,
        sanitized_json: str,
    ) -> SnapshotPayload: ...

    def render_targets(
        self,
        application_id: str,
        revision_id: str,
        html_artifact_version_id: str,
        pdf_artifact_version_id: str,
        screenshot_artifact_version_id: str,
        recruiter_pdf_filename: str,
    ) -> RenderTargets: ...

    def ingest_render_output(self, path: Path) -> SnapshotPayload:
        """Take one rendered output into storage and describe what was stored.

        Rendered HTML, PDF and screenshots are immutable payloads like any
        other, but they cannot be handed over as bytes: Chromium writes real
        files to the real paths `render_targets` hands it, so they arrive as a
        location rather than a value. This is the one place a `Path` travels
        *inward* to the store, and nothing comes back out - the returned
        reference is a storage-neutral string, exactly as `commit_snapshot`
        returns one.

        The hash describes the bytes that were stored, captured in the same
        read that stored them. A caller must register this `sha256` rather than
        re-hashing the file, or it records a digest for something other than
        what storage holds.
        """
        ...


class KnowledgeStore(Protocol):
    """Where canonical knowledge comes from, without saying it is files.

    Writes are prepared here but become visible only through the durable
    Knowledge mutation journal.
    """

    def load(self) -> Knowledge: ...

    def facts(self) -> Any: ...

    def task_contracts(self) -> TaskContracts: ...

    def stage_create_fact(
        self,
        mutation_id: str,
        source_name: str,
        payload: dict[str, Any],
        *,
        canonical: bool = False,
    ) -> tuple[StagedKnowledgeFile, Any]: ...

    def stage_promote_fact(
        self,
        mutation_id: str,
        fact_id: str,
        target: Any,
        *,
        explicitly_confirmed: bool,
    ) -> tuple[StagedKnowledgeFile, Any, Any]: ...

    def stage_attach_fact(
        self,
        mutation_id: str,
        profile: str,
        fact_id: str,
        section: str,
        *,
        pin: bool = False,
    ) -> tuple[StagedKnowledgeFile, Profile, str]: ...

    def stage_confirm_and_use_fact(
        self,
        mutation_id: str,
        fact_id: str,
        profile: str,
        section: str,
    ) -> tuple[list[StagedKnowledgeFile], Any, Any, Any, Profile, str, Knowledge]: ...

    def activate_staged(self, staged: StagedKnowledgeFile) -> None: ...

    def restore_staged(self, staged: StagedKnowledgeFile) -> None: ...

    def discard_staged(self, staged: StagedKnowledgeFile) -> None: ...

    def staged_from_mutation(self, mutation: KnowledgeMutation) -> StagedKnowledgeFile: ...

    def staged_file_state(self, staged: StagedKnowledgeFile) -> KnowledgeFileState: ...


class Renderer(Protocol):
    """HTML, PDF, and rendered-output validation.

    Kept behind a port because the browser is the slowest and least available
    dependency in the system: tests substitute it, and no application rule may
    depend on Playwright being present.
    """

    def render_html(
        self, draft: DraftDocument, output_path: Path, candidate: CandidateContext
    ) -> Path: ...

    def preview_html(self, draft: DraftDocument, candidate: CandidateContext) -> str: ...

    def render_pdf(
        self, html_path: Path, pdf_path: Path, screenshot_path: Path
    ) -> dict[str, Any]: ...

    def validate_rendered(
        self,
        draft: DraftDocument,
        profile: Profile,
        html_path: Path,
        pdf_path: Path,
        screenshot_path: Path,
        geometry: dict[str, Any],
        candidate: CandidateContext,
        delivered_pdf_filename: str | None = None,
    ) -> ValidationReport: ...

    def filename_for(self, normalized_role: str, candidate: CandidateContext) -> str: ...


ProposalT = TypeVar("ProposalT", bound=StrictModel)


@dataclass(frozen=True)
class AIProposal(Generic[ProposalT]):
    """What every AI task returns: a Proposal, and proof of what produced it.

    The two travel together because they are useless apart. A Proposal with no
    provenance cannot be audited, and provenance for a Proposal that was
    discarded records an execution nobody can point at.
    """

    proposal: ProposalT
    provenance: ProviderTaskResult


class JobAnalysisContext(StrictModel):
    """`propose_job_analysis`: this snapshot and what the rules already decided.

    The deterministic classification is supplied as context so the provider
    answers against what the engine found rather than from nothing. It cannot
    override it: the proposal contract is narrower than `JobAnalysis`, and
    `merge_classification` decides what survives.
    """

    job_text: str
    deterministic_classification: dict[str, Any]
    deterministic_gaps: list[dict[str, Any]] = []
    overrides: dict[str, str] = {}


class SelectionPlanContext(StrictModel):
    """`propose_selection_plan`: the analysis, and only the allowed facts.

    `allowed_facts` is the Profile's pool for this analysis, not the fact
    store. A provider that never sees a fact cannot select it, which is a
    stronger guarantee than checking afterwards that it did not.
    """

    job_analysis: dict[str, Any]
    allowed_facts: list[dict[str, Any]]
    deterministic_selection: dict[str, Any]


class DraftResumeContext(StrictModel):
    """`draft_resume`: the composed sections and the facts each one selected."""

    job_analysis: dict[str, Any]
    language: str
    sections: list[dict[str, Any]]
    allowed_facts: list[dict[str, Any]]


class RegenerateSectionContext(StrictModel):
    """`regenerate_section`: one named section of one exact draft version."""

    section: str
    language: str
    job_analysis: dict[str, Any]
    current_claims: list[dict[str, Any]]
    allowed_facts: list[dict[str, Any]]
    instruction: str = ""


class RegenerateClaimContext(StrictModel):
    """`regenerate_claim`: one named claim of one exact draft version."""

    claim_id: str
    section: str
    language: str
    job_analysis: dict[str, Any]
    current_text: str
    allowed_facts: list[dict[str, Any]]
    instruction: str = ""


class AIProvider(Protocol):
    """The five contracted AI tasks, as the application declares them.

    One method per task rather than one `run(task, payload)`, because the five
    take different inputs and return different Proposal types, and a single
    stringly-typed entry point makes that invisible at the call site. The
    transport - strict Structured Outputs over the Responses API - is an
    infrastructure concern behind `StructuredOutputClient`, and no rule in this
    layer may depend on it.

    Every method takes one explicit, minimal context and returns a Proposal
    with its provenance. Nothing here can save state: an implementation is
    handed no repository, no payload store, and no Workspace, so activation
    stays a decision the application commits (invariant 13).

    Calls are stateless. No method takes a conversation, a prior response ID,
    or anything that would make a second call depend on a first.
    """

    def propose_job_analysis(
        self, context: JobAnalysisContext
    ) -> AIProposal[JobClassificationProposal]: ...

    def propose_selection_plan(
        self, context: SelectionPlanContext
    ) -> AIProposal[SelectionProposal]: ...

    def draft_resume(self, context: DraftResumeContext) -> AIProposal[DraftProposal]: ...

    def regenerate_section(
        self, context: RegenerateSectionContext
    ) -> AIProposal[SectionProposal]: ...

    def regenerate_claim(self, context: RegenerateClaimContext) -> AIProposal[ClaimProposal]: ...
