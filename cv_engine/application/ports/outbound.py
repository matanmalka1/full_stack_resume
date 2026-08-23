"""What the application calls out to: files, knowledge, rendering, AI.

These are not repositories. They are the effects the application cannot
perform itself, declared as protocols so the deterministic workflow can run
against local adapters with no AI key present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ...domain.knowledge import Knowledge
from ...domain.models import (
    CandidateContext,
    DraftDocument,
    JobClassificationProposal,
    Profile,
    ValidationReport,
)
from ..knowledge_mutations import (
    KnowledgeFileState,
    KnowledgeMutation,
    StagedKnowledgeFile,
)
from .values import (
    DraftPaths,
    RenderTargets,
    RevisionPayloads,
    SnapshotPayload,
    StoredDraft,
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

    def render_targets(
        self,
        application_id: str,
        revision_id: str,
        html_artifact_version_id: str,
        pdf_artifact_version_id: str,
        screenshot_artifact_version_id: str,
        recruiter_pdf_filename: str,
    ) -> RenderTargets: ...


class KnowledgeStore(Protocol):
    """Where canonical knowledge comes from, without saying it is files.

    Writes are prepared here but become visible only through the durable
    Knowledge mutation journal.
    """

    def load(self) -> Knowledge: ...

    def facts(self) -> Any: ...

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


class ClassificationProvider(Protocol):
    """An AI provider's one v1 task, as a proposal the core may refuse."""

    def classify_job(self, payload: dict[str, Any], *, model: str) -> JobClassificationProposal: ...
